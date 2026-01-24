# Govee DreamView T1 (H6199) Ble client

[![version](https://img.shields.io/pypi/v/govee-h6199-ble)](https://pypi.org/project/govee-h6199-ble)
[![python version](https://img.shields.io/pypi/pyversions/govee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble)
[![license](https://img.shields.io/github/license/necrokote/pygovee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble/blob/main/LICENSE.txt)

This is a simple python client to control the Govee DreamView T1 (H6199) via BLE.


## Limitations
The client was tested on a device with **1.10.04 / 3.02.01** FW/HW versions.

Getting current mode would not return currently set color of a static mode and wouldn't distinguish specific music modes and their parameters. The former is caused by device responding with all zeroes, and the latter can be fixed in the future.

There is no support for setting colors for specific segments, nor controling the brightness for individual segments.

## Usage

The client uses `bleak` library and relies on it's `BleakClient` instance.
Client supports the following actions (from `govee_h6199_ble.commands` package):
- Get state
  - power
  - fw version
  - hw version
  - mac address
  - brightness
  - current mode
- Turn on/off
- Set brightness
- Set Static color mode
- Set Music color mode
  - Energic mode
  - Rythm mode
  - Spectrum mode
  - Rolling mode
- Set Video color mode
  - Movie mode
  - Game mode

More information can be found by inspecting the `govee_h6199_ble.commands` package.

### Example
```python
import asyncio

from bleak import BleakClient, BleakScanner

from govee_h6199_ble import (
    GetFirmwareVersion,
    GetHardwareVersion,
    GetPowerState,
    PowerOff,
    PowerOn,
    connected,
)


async def main():
    # scan and find first usable device
    devices = await BleakScanner.discover()
    named_devices = ((device, device.name) for device in devices if device.name)
    h6199_devices = (
        device for device, name in named_devices if name.startswith("Govee_H6199")
    )

    if first_device := next(h6199_devices, None):
        # connect
        async with BleakClient(first_device) as client:
            async with connected(client) as device:
                power = await device.send_command(GetPowerState())
                if power:
                    print("power on")

                    # get firmware version and turn device off
                    fw_version, hw_version, _ = await device.send_commands(
                        [GetFirmwareVersion(), GetHardwareVersion(), PowerOff()]
                    )

                    print(fw_version, hw_version)
                else:

                    # turn on
                    await device.send_command(PowerOn())


if __name__ == "__main__":
    asyncio.run(main())
```


## Exchanging raw frames
You can also exchange raw frames with the device using:
```python
async def exchange_frame(
    self,
    frame: bytes,
    timeouts: CommandTimeouts,
) -> bytes:...
```
and inspect responses manually.

> **Be aware**, if the command is not implemented on the device this call command will raise `asyncio.TimeoutError`, since response will not be received.

## Timeouts
By default, the client uses the following timeouts:
- command send timeout: None
- response receive timeout: 5 seconds

You can customize these timeouts by passing a `CommandTimeouts` instance to the `send_command(s)` calls.

## Credits
Govee for the device and the app.

https://github.com/Obi2000/Govee-H6199-Reverse-Engineering for the details of the protocol.

## Contributing

Both bug reports and pull requests are appreciated.