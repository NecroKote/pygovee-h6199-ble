import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from typing import NamedTuple, TypeVar, overload

from bleak import BleakClient
from bleak.exc import BleakError

from .errors import CommandTimeout, InvalidResponse, NotStarted, TransportError
from .protocol.base import Command, CommandWithParser
from .protocol.const import (
    UUID_CONTROL_CHARACTERISTIC,
    UUID_NOTIFY_CHARACTERISTIC,
    PacketHeader,
)
from .protocol.packet import make_frame, unpack_frame


def as_hex_string(v: bytes):
    return "".join(f"{x:02x}" for x in v)


T = TypeVar("T")


class CommandTimeouts(NamedTuple):
    """Write and response deadlines in seconds; a field of `None` waits forever."""

    write: float | None = None
    response: float | None = 5.0


_DEFAULT_TIMEOUTS = CommandTimeouts()


class Transport:
    """Low level BLE exchange: frames in, frames out. No device knowledge."""

    def __init__(self, client: BleakClient, logger: logging.Logger | None = None):
        self._log = logger or logging.getLogger(__name__)
        self._client = client

        self._lock = asyncio.Lock()
        self._notify_started = False
        self._lifecycle_lock = asyncio.Lock()
        self._pending_future: asyncio.Future[bytes] | None = None
        self._pending_command: int | None = None
        self._failure_handlers: list[Callable[[TransportError], None]] = []
        self._failed = False
        self._notification_handlers: list[Callable[[int, bytes], None]] = []
        #: `time.monotonic()` of the last frame sent
        self.last_activity = 0.0
        #: `time.monotonic()` of the last frame received, response or
        #: notification; `None` until one arrives
        self.last_received: float | None = None

    async def start(self):
        self._log.debug("start ...")
        async with self._lifecycle_lock:
            if self._notify_started:
                self._log.debug("already started")
                return

            try:
                await self._client.start_notify(
                    UUID_NOTIFY_CHARACTERISTIC, self._handle_response
                )
            except TimeoutError as error:
                raise CommandTimeout(
                    "starting notifications timed out", "start"
                ) from error
            except (BleakError, OSError) as error:
                raise self._transport_error(error) from error

            self._failed = False

            self._notify_started = True

        self._log.debug("start done")

    async def stop(self):
        self._log.debug("stop ...")

        async with self._lifecycle_lock:
            if not self._notify_started:
                self._log.debug("already stopped")
                return

            self._notify_started = False
            pending = self._pending_future
            if pending is not None and not pending.done():
                pending.set_exception(NotStarted("transport stopped during a command"))
            self._log.debug("stopping notify ...")
            try:
                if self._client.is_connected:
                    await self._client.stop_notify(UUID_NOTIFY_CHARACTERISTIC)
            except (BleakError, OSError):
                self._log.debug("could not stop notify, link is gone")

            self._notify_started = False

        self._log.debug("stop done")

    def add_notification_handler(
        self, handler: Callable[[int, bytes], None]
    ) -> Callable[[], None]:
        """
        Be called with `(id, payload)` for every frame the device sends on its
        own (header 0xEE). `payload` is frame bytes 2-18.

        Returns a function that removes the handler.
        """

        self._notification_handlers.append(handler)
        removed = False

        def remove():
            nonlocal removed
            if not removed:
                self._notification_handlers.remove(handler)
                removed = True

        return remove

    def add_failure_handler(self, handler: Callable[[TransportError], None]):
        """Receive a detected BLE failure once per started session."""
        self._failure_handlers.append(handler)
        removed = False

        def remove():
            nonlocal removed
            if not removed:
                self._failure_handlers.remove(handler)
                removed = True

        return remove

    def _transport_error(self, error: Exception) -> TransportError:
        failure = TransportError(str(error))
        self._notify_started = False
        if not self._failed:
            self._failed = True
            for handler in list(self._failure_handlers):
                try:
                    handler(failure)
                except Exception:  # noqa: BLE001 - isolate client callbacks
                    self._log.exception("failure handler failed")
        return failure

    def _handle_response(self, _, data: bytearray):
        self.last_received = time.monotonic()
        if len(data) >= 2 and data[0] == PacketHeader.NOTIFICATION:
            # never a reply, even if the id looks like the pending command
            for handler in list(self._notification_handlers):
                try:
                    handler(data[1], bytes(data[2:19]))
                except Exception:  # noqa: BLE001 - isolate client callbacks
                    self._log.exception("notification handler failed")
            return

        pending = self._pending_future
        if pending is None or pending.done():
            return

        # ignore notifications answering some other command
        if len(data) < 2 or data[1] != self._pending_command:
            self._log.debug(f"ignoring unrelated notification {as_hex_string(data)}")
            return

        pending.set_result(bytes(data))

    async def exchange_frame(
        self,
        frame: bytes,
        timeouts: CommandTimeouts,
    ):
        self._log.debug(f"exchange_frame frame={as_hex_string(frame)}")

        if not self._notify_started:
            raise NotStarted("call start() or use async with before sending commands")
        async with self._lock:
            if not self._notify_started:
                raise NotStarted("transport stopped while waiting to send")
            if not self._client.is_connected:
                raise self._transport_error(BleakError("BLE client is disconnected"))
            self._pending_command = frame[1]
            self.last_activity = time.monotonic()
            self._pending_future = asyncio.get_running_loop().create_future()

            self._log.debug("sending ...")
            phase = "write"
            try:
                await asyncio.wait_for(
                    # HINT: was using response=True before but it seems not needed
                    self._client.write_gatt_char(
                        UUID_CONTROL_CHARACTERISTIC, frame, response=False
                    ),
                    timeout=timeouts.write,
                )

                phase = "response"
                self._log.debug("sent, waiting for response ...")
                result = await asyncio.wait_for(
                    self._pending_future, timeout=timeouts.response
                )

                header, command, payload = unpack_frame(result)
                self._log.debug(
                    f"response header={header:02x} cmd={command:02x} payload={as_hex_string(payload)}"
                )

                self._log.debug(f"response received result={as_hex_string(result)}")
                return payload

            except TimeoutError as error:
                raise CommandTimeout(f"command {phase} timed out", phase) from error
            except (BleakError, OSError) as error:
                raise self._transport_error(error) from error
            except ValueError as error:
                raise InvalidResponse(str(error)) from error
            finally:
                if self._pending_future is not None:
                    if not self._pending_future.done():
                        self._pending_future.cancel()
                    elif not self._pending_future.cancelled():
                        self._pending_future.exception()
                self._pending_future = None
                self._pending_command = None

    @overload
    async def send_command(
        self,
        command: CommandWithParser[T],
        timeouts: CommandTimeouts = _DEFAULT_TIMEOUTS,
    ) -> T: ...

    @overload
    async def send_command(
        self,
        command: CommandWithParser[T],
        timeouts: None,
    ) -> None | T: ...

    @overload
    async def send_command(
        self,
        command: Command,
        timeouts: CommandTimeouts = _DEFAULT_TIMEOUTS,
    ) -> bytes: ...

    @overload
    async def send_command(
        self,
        command: Command,
        timeouts: None,
    ) -> None | bytes: ...

    async def send_command(
        self, command: Command, timeouts: CommandTimeouts | None = _DEFAULT_TIMEOUTS
    ):
        """
        Sends a command and waits for its response.

        If the command is an instance of CommandWithParser, the response will be
        parsed using the command's parse_response method.

        If timeouts is `None`, use the default deadlines and return `None`
        on timeout. `CommandTimeouts(None, None)` disables both deadlines.
        """

        self._log.debug(f"send_command cmd={command}")

        header, domain, payload = command.payload()
        frame = make_frame(header, domain, payload or [])

        effective_timeouts = timeouts if timeouts is not None else CommandTimeouts()
        try:
            response = await self.exchange_frame(frame, effective_timeouts)
        except CommandTimeout:
            if timeouts is None:
                return None

            raise

        if isinstance(command, CommandWithParser):
            try:
                return command.parse_response(response)
            except (ValueError, IndexError, TypeError) as error:
                raise InvalidResponse(f"{type(command).__name__}: {error}") from error

        return response

    async def send_commands(
        self,
        commands: Sequence[Command],
        command_timeouts: CommandTimeouts | None = _DEFAULT_TIMEOUTS,
    ):
        """
        Sends multiple commands sequentially and waits for their responses.
        Returns a list of responses corresponding to each command.

        If the command is an instance of CommandWithParser, the response will be
        parsed using the command's parse_response method.

        If command_timeouts is `None`, the method will return `None` for any command that
        times out instead of raising an exception.
        """

        responses = []
        for command in commands:
            result = await self.send_command(command, command_timeouts)
            responses.append(result)

        return responses
