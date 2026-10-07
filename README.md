# Govee DreamView T1 (H6199) BLE client

[![version](https://img.shields.io/pypi/v/govee-h6199-ble)](https://pypi.org/project/govee-h6199-ble)
[![python version](https://img.shields.io/pypi/pyversions/govee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble)
[![license](https://img.shields.io/github/license/necrokote/pygovee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble/blob/main/LICENSE)

Control the Govee DreamView T1 (H6199) from Python over Bluetooth Low Energy (BLE).

## Install

Python 3.11 or newer is required.

```sh
python -m pip install govee-h6199-ble
```

## Usage

Pass an already connected `BleakClient` to `GoveeH6199`. The library reads device information when first needed and selects commands appropriate for the device’s firmware and protocol generation. A capability-gated operation raises `UnsupportedFeature` if the required capability is unavailable. See [capabilities](docs/capabilities.md) for details.

## Limitations

Scenes and DIY are not supported. Music sensitivity, fixed color and the calm flag cannot be read back. See [hardware coverage](docs/advanced.md#hardware-coverage) for tested firmware.

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

The outer context manages the Bluetooth connection; the inner context starts notifications and keep-alive. See [connection](docs/connection.md) for details.

See the [usage walkthrough](docs/usage.md) for more features and the interactive device check.

## Documentation

Start with the [documentation homepage](docs/index.md).

## Credits

Govee for the device and the app.

https://github.com/Obi2000/Govee-H6199-Reverse-Engineering for the details of the protocol.

## Contributing

Both bug reports and pull requests are appreciated.
