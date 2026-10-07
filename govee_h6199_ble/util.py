import logging
from contextlib import asynccontextmanager

from bleak import BleakClient

from .capabilities import DeviceInfo
from .device import GoveeH6199
from .transport import _DEFAULT_TIMEOUTS, CommandTimeouts


@asynccontextmanager
async def connected(
    client: BleakClient,
    logger: logging.Logger | None = None,
    device_info: DeviceInfo | None = None,
    timeouts: CommandTimeouts = _DEFAULT_TIMEOUTS,
    keep_alive_interval: float | None = 5.0,
    optional_response_timeout: float | None = 2.0,
):
    """Start a facade on an already connected Bleak client; forwards its options."""
    async with GoveeH6199(
        client,
        logger,
        device_info,
        timeouts,
        keep_alive_interval,
        optional_response_timeout,
    ) as device:
        yield device
