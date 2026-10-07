from contextlib import asynccontextmanager

from bleak import BleakClient

from .device import GoveeH6199


@asynccontextmanager
async def connected(client: BleakClient):
    async with GoveeH6199(client) as device:
        yield device
