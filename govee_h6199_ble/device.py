import asyncio
import logging
from functools import partial
from typing import TypeVar, overload

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

from .commands import Command, CommandWithParser
from .const import UUID_CONTROL_CHARACTERISTIC, UUID_NOTIFY_CHARACTERISTIC


def as_hex_string(v: bytes):
    return "".join((f"{x:02x}" for x in v))


T = TypeVar("T")


class GoveeH6199:
    def __init__(self, client: BleakClient):
        self._log = logging.getLogger(f"govee.h6199.{client.address[-4:]}")
        self._client = client

        self._loop = asyncio.get_running_loop()
        self._pending_commands: dict[tuple, asyncio.Future[bytes]] = {}

    async def start(self):
        await self._client.start_notify(
            UUID_NOTIFY_CHARACTERISTIC, self._handle_response
        )

    async def stop(self):
        await self._client.stop_notify(UUID_NOTIFY_CHARACTERISTIC)

    def _handle_response(self, sender: BleakGATTCharacteristic, data: bytearray):
        cmd = data[0]
        group = data[1]
        payload = bytes(data[2:-1])

        self._log.debug(
            f"recv: {as_hex_string(data)} (cmd={cmd:02x} group={group:02x})"
        )
        if waiting := self._pending_commands.get((cmd, group)):
            waiting.set_result(payload)

    def _cs(self, data: bytes):
        checksum = 0
        for b in data:
            checksum ^= b
        return checksum & 0xFF

    def _frame(self, cmd: int, group: int, payload: list[int]) -> bytes:
        if len(payload) > 17:
            raise ValueError("Payload too long")

        frame = bytearray(20)
        frame[0] = cmd
        frame[1] = group & 0xFF

        for idx, byte in enumerate(payload):
            frame[idx + 2] = byte

        frame[19] = self._cs(frame[:-1])

        return bytes(frame)

    def _on_timeout(self, future: asyncio.Future[bytes]):
        if not future.done():
            future.set_exception(asyncio.TimeoutError("Timeout waiting for response"))

    async def command_with_reply(
        self, cmd: int, group: int, payload: list[int] | None = None, timeout=5.0
    ):
        frame = self._frame(cmd, group, payload or [])
        if _ := self._pending_commands.get(frame):
            self._log.warning(f"({cmd}, {group}) already pending response")
            raise ValueError("already pending response")

        key = (cmd, group)
        future: asyncio.Future[bytes] = self._loop.create_future()
        self._pending_commands[key] = future

        self._log.debug(f"send: {as_hex_string(frame)}")
        await self._client.write_gatt_char(
            UUID_CONTROL_CHARACTERISTIC, frame, response=True
        )

        timer_handle = self._loop.call_later(timeout, partial(self._on_timeout, future))
        try:
            await future
        finally:
            self._pending_commands.pop(key, None)
            timer_handle.cancel()

        return future.result()

    @overload
    async def send_command(self, command: CommandWithParser[T]) -> T: ...

    @overload
    async def send_command(
        self, command: CommandWithParser[T], timeout: float
    ) -> T: ...

    async def send_command(self, command: Command, timeout: float = 5.0):
        cmd, group, payload = command.payload()
        response = await self.command_with_reply(cmd, group, payload, timeout)

        if isinstance(command, CommandWithParser):
            return command.parse_response(response)

        return response

    async def send_commands(self, commands: list[Command], timeout: float = 5.0):
        for command in commands:
            cmd, group, payload = command.payload()
            await self.command_with_reply(cmd, group, payload, timeout)
