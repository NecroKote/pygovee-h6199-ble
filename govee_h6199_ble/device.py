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
    def __init__(self, client: BleakClient, logger: logging.Logger | None = None):
        self._log = logger or logging.getLogger(__name__)
        self._client = client

        self._loop = asyncio.get_running_loop()
        self._pending_commands: dict[tuple[int, int], asyncio.Future[bytes]] = {}

    async def start(self):
        await self._client.start_notify(
            UUID_NOTIFY_CHARACTERISTIC, self._handle_response
        )

    async def stop(self):
        if self._client.is_connected:
            await self._client.stop_notify(UUID_NOTIFY_CHARACTERISTIC)

    def _handle_response(self, sender: BleakGATTCharacteristic, data: bytearray):
        cmd = data[0]
        group = data[1]
        payload = bytes(data[2:-1])

        self._log.debug(
                f"recv: {as_hex_string(data)} (cmd={cmd:02x} group={group:02x})"
           )
        # Pop the waiter so a duplicate notification won't try to complete it again.
        waiting = self._pending_commands.pop((cmd, group), None)
        if waiting is None:
                return  # stray/late notify; nothing pending for this (cmd, group)
        try:
                # Complete only if still pending.
            if not waiting.cancelled() and not waiting.done():
                    waiting.set_result(payload)
        except asyncio.InvalidStateError:
            # Already completed/cancelled elsewhere; ignore duplicate/late notify.
            pass

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
        key = (cmd, group)
        frame = self._frame(cmd, group, payload or [])
        if _ := self._pending_commands.get(key):
            self._log.warning(f"({cmd}, {group}) already pending response")
            raise ValueError("already pending response")
        # If a previous waiter exists for the same key, cancel and replace it
        old = self._pending_commands.pop(key, None)
        if old is not None and not old.done():
            old.cancel()

        future: asyncio.Future[bytes] = self._loop.create_future()
        self._pending_commands[key] = future

        self._log.debug(f"send: {as_hex_string(frame)}")
        await self._client.write_gatt_char(
            UUID_CONTROL_CHARACTERISTIC, frame, response=True
        )

        # Schedule timeout only when timeout >= 0 (no-timeout when timeout == -1)
        timer_handle = None
        if timeout is None:
                timeout = -1
        if timeout >= 0:
                timer_handle = self._loop.call_later(timeout, partial(self._on_timeout, future))
        try:
            await future
        finally:
            # Only remove if it still points to *this* future
            cur = self._pending_commands.get(key)
            if cur is future:
                self._pending_commands.pop(key, None)
            if timer_handle is not None:
                timer_handle.cancel()

        return future.result()

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
