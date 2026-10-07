# Govee H6199 BLE

Control a Govee DreamView T1 (H6199) from Python over Bluetooth Low Energy: power, brightness, colors, zones, music mode and video mode (camera-driven lighting).

## Install

Python 3.11 or newer is required.

```sh
python -m pip install govee-h6199-ble
```

The library uses [Bleak](https://bleak.readthedocs.io/) for the Bluetooth connection. Run it on a computer with Bluetooth access to the light.

## Quick start

```python
import asyncio

from bleak import BleakClient, BleakScanner
from govee_h6199_ble import GoveeH6199


async def main():
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: bool(d.name and d.name.startswith("Govee_H6199"))
    )
    if device is None:
        print("no H6199 found")
        return

    async with BleakClient(device) as client:
        async with GoveeH6199(client) as light:
            await light.set_power(True)
            await light.set_brightness(60)
            await light.set_static_color((255, 80, 0))
            print(await light.read_state())

            caps = await light.get_capabilities()
            if caps.white_balance:
                await light.set_white_balance(10)


if __name__ == "__main__":
    asyncio.run(main())
```

See the [usage walkthrough](usage.md) for more features and the interactive device check.

The outer context manages the Bluetooth connection; the inner context starts notifications and keep-alive. Device errors derive from `GoveeError`; invalid inputs raise `ValueError`. See [connection](connection.md) and [errors](errors.md) for details.

## Limitations

Scenes and DIY are not supported. Music sensitivity, fixed color and the calm flag cannot be read back. Hardware verification is limited; see [hardware coverage](advanced.md#hardware-coverage).

## More documentation

- [Usage walkthrough](usage.md): examples of the main features.
- [Capabilities](capabilities.md): supported actions, firmware checks and overrides.
- [API reference](api.md): values, return types and firmware-specific behavior.
- [Connection](connection.md): lifecycle and keep-alive.
- [Device events](events.md): listeners and disconnect notifications.
- [Errors](errors.md): exceptions raised by the library.
- [Timeouts](timeouts.md): command deadlines and optional reads.
- [Advanced](advanced.md): hardware coverage, limitations and raw commands.
- [Upgrading](upgrading.md): migration from earlier versions.
