# Govee DreamView T1 (H6199) Ble client

[![version](https://img.shields.io/pypi/v/govee-h6199-ble)](https://pypi.org/project/govee-h6199-ble)
[![python version](https://img.shields.io/pypi/pyversions/govee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble)
[![license](https://img.shields.io/github/license/necrokote/pygovee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble/blob/main/LICENSE.txt)

This is a simple python client to control the Govee DreamView T1 (H6199) via BLE.


## Usage

The client uses `bleak` library and relies on it's `BleakClient` instance.
Client supports the following actions (from `govee_h6199_ble.commands` package):
- Get state
  - power
  - fw version
  - hw version
  - mac address
  - brightness
  - color mode
- Turn on/off
- Set brightness
- Set Static color
- Set Music color mode
  - Energic mode
  - Rythm mode
  - Spectrum mode
  - Rolling mode
- Set Video color mode

Example:
```python
from bleak import BleakClient, BleakScanner
from govee_h6199_ble import GoveeH6199, GetFirmwareVersion, PowerOn, PowerOff

if __name__ == '__main__':
    # scan and find first usable device
    devices = await BleakScanner.discover()
    named_devices = (device for device in devices if device.name)
    h6199_devices = (
        device for device in named_devices
        if device.name.startswith("Govee_H6199")
    )

    if device := next(h6199_devices, None):
        # connect
        async with BleakClient(first_device) as client:
            async with connected(client) as h6199:
                power = await device.send_command(GetPowerState())
                if power:
                    print("power on")

                    # get firmware version
                    fw_version = await h6199.get(GetFirmwareVersion())
                    print(fw_version)

                    # turn off
                    await h6199.set(PowerOff())
                else:

                    # turn on
                    await h6199.set(PowerOn())
```

You can also run raw commands using:
```python
async def command_with_reply(
    self,
    cmd: int,
    group: int,
    payload: list[int] | None = None,
    timeout=5.0,
) -> bytes:...
```
and inspect responses manually.
Be aware, if the command is not implemented in the device this call command will raise `asyncio.TimeoutError`, since response will not be received.

## Credits
Govee for the device and the app.

https://github.com/Obi2000/Govee-H6199-Reverse-Engineering for the details of the protocol.

## Contributing

Both bug reports and pull requests are appreciated.