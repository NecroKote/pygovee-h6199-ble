from contextlib import asynccontextmanager

from bleak import BleakClient

from .device import GoveeH6199


@asynccontextmanager
async def connected(client: BleakClient):
    device = GoveeH6199(client)
    await device.start()

    try:
        yield device
    finally:
        await device.stop()
