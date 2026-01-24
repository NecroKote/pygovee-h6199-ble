import asyncio
import logging
from typing import NamedTuple, Sequence, TypeVar, overload

from bleak import BleakClient

from .commands import Command, CommandWithParser
from .const import UUID_CONTROL_CHARACTERISTIC, UUID_NOTIFY_CHARACTERISTIC
from .packet import make_frame, unpack_frame


def as_hex_string(v: bytes):
    return "".join((f"{x:02x}" for x in v))


T = TypeVar("T")


class CommandTimeouts(NamedTuple):
    """Timeouts for a command in seconds."""

    write: float | None = None
    response: float | None = 5.0


class GoveeH6199:
    def __init__(self, client: BleakClient, logger: logging.Logger | None = None):
        self._log = logger or logging.getLogger(__name__ + "@" + str(id(self)))
        self._client = client

        self._lock = asyncio.Lock()
        self._notify_started = False
        self._notify_condition = asyncio.Condition()
        self._pending_future: asyncio.Future[bytes] | None = None

    async def start(self):
        self._log.debug("start ...")
        async with self._notify_condition:
            if self._notify_started:
                self._log.debug("already started")
                return

            await self._client.start_notify(
                UUID_NOTIFY_CHARACTERISTIC, self._handle_response
            )

            self._notify_started = True
            self._notify_condition.notify_all()

        self._log.debug("start done")

    async def stop(self):
        self._log.debug("stop ...")

        async with self._notify_condition:
            if not self._notify_started:
                self._log.debug("already stopped")
                return

            self._log.debug("stopping notify ...")
            await self._client.stop_notify(UUID_NOTIFY_CHARACTERISTIC)

            self._notify_started = False
            self._notify_condition.notify_all()

        self._log.debug("stop done")

    def _handle_response(self, _, data: bytearray):
        if pending := self._pending_future:
            pending.set_result(data)

    async def exchange_frame(
        self,
        frame: bytes,
        timeouts: CommandTimeouts,
    ):
        self._log.debug(f"exchange_frame frame={as_hex_string(frame)}")

        await self._notify_condition.wait_for(lambda: self._notify_started)
        async with self._lock:
            self._pending_future = asyncio.get_running_loop().create_future()

            self._log.debug("sending ...")
            try:
                await asyncio.wait_for(
                    # HINT: was using response=True before but it seems not needed
                    self._client.write_gatt_char(UUID_CONTROL_CHARACTERISTIC, frame),
                    timeout=timeouts.write,
                )

                self._log.debug("sent, waiting for response ...")
                result = await asyncio.wait_for(
                    self._pending_future, timeout=timeouts.response
                )

                cmd, group, payload = unpack_frame(result)
                self._log.debug(
                    f"response cmd={cmd:02x} group={group:02x} frame={as_hex_string(payload)})"
                )

                self._log.debug(f"response received result={as_hex_string(result)}")
                return payload

            finally:
                self._pending_future = None

    @overload
    async def send_command(
        self,
        command: CommandWithParser[T],
        timeouts: CommandTimeouts = CommandTimeouts(),
    ) -> T: ...

    @overload
    async def send_command(
        self,
        command: CommandWithParser[T],
        timeouts=None,
    ) -> None | T: ...

    @overload
    async def send_command(
        self,
        command: Command,
        timeouts: CommandTimeouts = CommandTimeouts(),
    ) -> bytes: ...

    @overload
    async def send_command(
        self,
        command: Command,
        timeouts=None,
    ) -> None | bytes: ...

    async def send_command(
        self, command: Command, timeouts: CommandTimeouts | None = CommandTimeouts()
    ):
        """
        Sends a command and waits for its response.

        If the command is an instance of CommandWithParser, the response will be
        parsed using the command's parse_response method.

        If timeouts is `None`, the method will return `None` on timeout instead of raising
        an exception.
        """

        self._log.debug(f"send_command cmd={command}")

        cmd, group, payload = command.payload()
        frame = make_frame(cmd, group, payload or [])

        effective_timeouts = timeouts or CommandTimeouts(None, None)
        try:
            response = await self.exchange_frame(frame, effective_timeouts)
        except asyncio.TimeoutError:
            if timeouts is None:
                return None

            raise

        if isinstance(command, CommandWithParser):
            return command.parse_response(response)

        return response

    async def send_commands(
        self,
        commands: Sequence[Command],
        command_timeouts: CommandTimeouts | None = CommandTimeouts(),
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
