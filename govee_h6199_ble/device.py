import asyncio
import logging
from typing import TypeVar, overload

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from .commands import Command, CommandWithParser
from .const import UUID_CONTROL_CHARACTERISTIC, UUID_NOTIFY_CHARACTERISTIC
from .packet import make_frame


def as_hex_string(v: bytes):
    return "".join((f"{x:02x}" for x in v))


T = TypeVar("T")


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

    def _handle_response(self, sender: BleakGATTCharacteristic, data: bytearray):
        if (pending := self._pending_future) is None:
            raise RuntimeError("Received notification with no pending command")

        cmd, group, *payload, _ = data
        self._log.debug(
            f"response cmd={cmd:02x} group={group:02x} frame={as_hex_string(data)})"
        )

        pending.set_result(bytes(payload))

    async def command_with_reply(
        self,
        cmd: int,
        group: int,
        payload: list[int] | None = None,
        timeout: float | None = 5.0,
    ):
        frame = make_frame(cmd, group, payload or [])

        self._log.debug(
            f"command_with_reply cmd={cmd:02x} group={group:02x} frame={as_hex_string(frame)}"
        )

        await self._notify_condition.wait_for(lambda: self._notify_started)
        async with self._lock:
            self._pending_future = asyncio.get_running_loop().create_future()

            self._log.debug("sending ...")
            try:
                await self._client.write_gatt_char(
                    UUID_CONTROL_CHARACTERISTIC, frame, response=True
                )

                self._log.debug("sent, waiting for response ...")
                result = await asyncio.wait_for(self._pending_future, timeout=timeout)
                self._log.debug("response resolved")
                return result

            finally:
                self._pending_future = None

    @overload
    async def send_command(self, command: CommandWithParser[T]) -> T: ...

    @overload
    async def send_command(
        self, command: CommandWithParser[T], timeout: float
    ) -> T: ...

    @overload
    async def send_command(
        self, command: CommandWithParser[T], timeout=-1
    ) -> None | T: ...

    async def send_command(self, command: Command, timeout: float = 5.0):
        """
        Sends a command and waits for its response.

        If the command is an instance of CommandWithParser, the response will be
        parsed using the command's parse_response method.

        If timeout is -1, the method will return `None` on timeout instead of raising
        an exception.
        """

        self._log.debug(f"send_command cmd={command}")
        cmd, group, payload = command.payload()
        try:
            response = await self.command_with_reply(cmd, group, payload, timeout)
        except asyncio.TimeoutError:
            if timeout == -1:
                return None

            raise

        if isinstance(command, CommandWithParser):
            return command.parse_response(response)

        return response

    async def send_commands(self, commands: list[Command], timeout: float = 5.0):
        for command in commands:
            cmd, group, payload = command.payload()
            try:
                await self.command_with_reply(cmd, group, payload, timeout)
            except asyncio.TimeoutError:
                if timeout == -1:
                    pass

                raise
