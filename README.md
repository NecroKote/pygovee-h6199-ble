# Govee DreamView T1 (H6199) Ble client

[![version](https://img.shields.io/pypi/v/govee-h6199-ble)](https://pypi.org/project/govee-h6199-ble)
[![python version](https://img.shields.io/pypi/pyversions/govee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble)
[![license](https://img.shields.io/github/license/necrokote/pygovee-h6199-ble)](https://github.com/NecroKote/pygovee-h6199-ble/blob/main/LICENSE.txt)

This is a simple python client to control the Govee DreamView T1 (H6199) via BLE.


## Limitations
The client was tested on a device with **1.10.04 / 3.02.01** FW/HW versions (Wi-Fi 1.00.33 / 1.03.00): power, brightness, static colors and zones, video and music modes, white balance, edge brightness, gradient. Everything else follows the reverse-engineered protocol notes and is not verified on hardware:
- pact V1 devices (legacy color mode, 1-254 brightness)
- feature detection that needs the Wi-Fi chip versions (cmd `0x20` / `0x21`)
- whole-screen video brightness on other hardware revisions
- the WiFi chip version reads used for feature detection

In the static color mode `get_mode()` also reads the zone colors (cmd `0xA5`), which works on the tested firmware. `StaticColorMode.kind` is always `None` there (the device reports 0).

Specific music parameters are not read back. Scenes and DIY are not supported.

## Usage

The client uses the `bleak` library and relies on its `BleakClient` instance.
`GoveeH6199` is the only class most code needs. It reads the device versions on first use of a version dependent feature and picks the right frames for that firmware. A feature the device can't do raises `UnsupportedFeature`.

- Info: power, firmware / hardware version, MAC, pact, brightness, current mode, zones, `read_state()`
- `set_power`, `set_brightness`
- `set_static_color`, `set_color_temperature` (2000-9000 K, rounded to the nearest table value), `set_zone_colors`, `set_zone_brightness`, `set_zone_brightnesses`, `set_gradient`
- `set_music_mode` (rhythm, spectrum, energic, rolling)
- `set_video_mode`, `set_video_brightness`, `set_video_edge_brightness` / `get_video_edge_brightness`, white balance: `set_white_balance(step)` (20 defined steps), `set_white_balance_auto`, `reset_white_balance`, `get_white_balance`; black screen (what happens when the picture goes black): `get_black_screen`, `set_black_screen`, `update_black_screen`; `set_white_balance_raw` takes red / blue 1-31, the device ignores anything else
- `get_capabilities()` tells which of the above the device supports

Zones are numbered 0-14.

### Device events
The device reports some changes on its own (header `0xEE`): power, brightness, Wi-Fi state, movie mode. Register a listener to receive them as typed events:
```python
remove = light.add_listener(lambda event: print(event))  # PowerChanged(on=True), BrightnessChanged(55), ...
```
The device drops a connection that has been idle for about 10 s, so while started the client sends a power read after `keep_alive_interval` (5 s by default, `None` disables) of silence. Events are decoded from the spec only; none have been seen from the tested device yet, and our own writes don't trigger them.

### Quick start

Everything the client can do, in order: connect, read properties and capabilities, then the actions. Actions in the second group depend on the firmware, so they are guarded by a `caps.*` flag. Without the capability the call raises `UnsupportedFeature`, which the last block shows.

```python
import asyncio

from bleak import BleakClient, BleakScanner

from govee_h6199_ble import (
    BlackScreenMode,
    GoveeH6199,
    MusicMode,
    UnsupportedFeature,
)


async def main():
    # find the first H6199 in range
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: bool(d.name and d.name.startswith("Govee_H6199"))
    )
    if device is None:
        print("no H6199 found")
        return

    # connect over BLE
    async with BleakClient(device) as client:
        # start the client (notifications, keep-alive), stopped again on exit
        async with GoveeH6199(client) as light:
            # --- properties -------------------------------------------------

            # read the firmware, hardware and Wi-Fi chip versions and the pact once
            info = await light.get_device_info()
            print(f"firmware {info.soft}, hardware {info.hard}")
            print(f"wifi firmware {info.wifi_soft}, wifi hardware {info.wifi_hard}")
            print(f"pact {info.pact}, generation {info.pact and info.pact.generation!r}")

            # read the MAC address of the Wi-Fi chip
            print("mac", await light.get_mac_address())

            # read power, brightness, current mode and the 15 zones in one go
            print(await light.read_state())

            # --- capabilities -----------------------------------------------

            # work out what this firmware supports (cached after the first call)
            caps = await light.get_capabilities()
            print(caps)

            # --- events -----------------------------------------------------

            # print what the device reports on its own, e.g. changes made from a remote
            remove_listener = light.add_listener(print)

            # --- actions every device supports ------------------------------

            # turn the light on
            await light.set_power(True)

            # set the overall brightness, 1-100
            await light.set_brightness(60)

            # paint all zones in one color
            await light.set_static_color((255, 80, 0))

            # use a color temperature; any 2000-9000 K, rounded to the nearest table value
            await light.set_color_temperature(3000)

            # change the color temperature of the middle zone only (zones are 0-14)
            await light.set_color_temperature(6500, zones=[7])

            # paint each zone: left half red, right half blue
            red, blue = (255, 0, 0), (0, 0, 255)
            await light.set_zone_colors(
                {**{zone: red for zone in range(7)}, **{zone: blue for zone in range(8, 15)}}
            )

            # read back the mode; in the static mode it carries color and temperature per zone
            mode = await light.get_mode()
            print(mode, [zone.kelvin for zone in mode.zones or []])

            # blend the colors of neighbouring zones
            await light.set_gradient(True)
            print("gradient", await light.get_gradient())

            # switch to the music mode, rhythm effect, soft, automatic colors
            await light.set_music_mode(MusicMode.RYTHM, sensitivity=50, calm=True)

            # switch to the music mode, spectrum effect with a fixed color
            await light.set_music_mode(MusicMode.SPECTRUM, sensitivity=70, color=(0, 255, 0))

            # switch to the music mode, energic effect
            await light.set_music_mode(MusicMode.ENERGIC, sensitivity=70)

            # switch to the music mode, rolling effect with a fixed color
            await light.set_music_mode(MusicMode.ROLLING, sensitivity=70, color=(255, 0, 255))

            # switch to the video mode: whole screen, movie, saturation, sound effects and their softness
            await light.set_video_mode(
                full_screen=True,
                game_mode=False,
                saturation=70,
                sound_effects=True,
                sound_effects_softness=30,
            )

            # --- actions that depend on the firmware ------------------------

            # needs caps.zone_brightness (not available on pact V1 devices)
            if caps.zone_brightness:
                # set the brightness of zones 0 and 14, 1-100
                await light.set_zone_brightness(40, zones=[0, 14])

                # set the brightness of every zone, 15 values
                await light.set_zone_brightnesses([100 - 5 * zone for zone in range(15)])

            # needs caps.video_brightness or caps.video_segment_brightness
            if caps.video_brightness or caps.video_segment_brightness:
                # set the video mode brightness, the client picks the command the firmware has
                await light.set_video_brightness(70)

            # needs caps.video_segment_brightness (hardware 3.02.01 / 3.02.10, recent firmware)
            if caps.video_segment_brightness:
                # set the relative brightness of each screen edge, 1-100
                await light.set_video_edge_brightness(left=100, top=100, right=100, bottom=50)

                # read the edge brightness back
                print(await light.get_video_edge_brightness())

            # needs caps.white_balance
            if caps.white_balance:
                # set the video white balance to step 10 of the 20 defined steps
                await light.set_white_balance(10)

                # read the white balance; `step` is its position among the 20 steps, `default` the device's own
                state = await light.get_white_balance()
                print(state.current, state.current.step, state.default)

                # let the device choose the white balance, the stored step is kept
                await light.set_white_balance_auto()

                # go back to the device's default white balance
                await light.reset_white_balance()

            # needs caps.black_screen, the same firmware as the edge brightness
            if caps.black_screen:
                # keep the same tone for 5 minutes when the picture goes black
                await light.update_black_screen(
                    enabled=True, mode=BlackScreenMode.SAME_TONE, same_tone_seconds=300
                )

                # read the black screen setting back
                print(await light.get_black_screen())

            # --- what a missing capability looks like -----------------------

            # a device without the capability raises here instead of sending something unknown
            try:
                await light.set_video_edge_brightness(left=50, top=50, right=50, bottom=50)
            except UnsupportedFeature as error:
                print("not available on this firmware:", error)

            # --- cleanup ----------------------------------------------------

            # stop listening for events
            remove_listener()

            # turn the light off
            await light.set_power(False)


if __name__ == "__main__":
    asyncio.run(main())
```

Which capability enables what:

| Capability | Actions |
|---|---|
| none, every device | power, overall brightness, static color, color temperature, zone colors, gradient, music modes, video mode, reads of the mode and zones |
| `zone_brightness` | `set_zone_brightness`, `set_zone_brightnesses` |
| `video_brightness` / `video_segment_brightness` | `set_video_brightness` |
| `video_segment_brightness` | `set_video_edge_brightness`, `get_video_edge_brightness` |
| `white_balance` | `set_white_balance`, `set_white_balance_auto`, `reset_white_balance`, `get_white_balance` |
| `black_screen` | `get_black_screen`, `set_black_screen`, `update_black_screen` |

Calling a gated method on a device without the capability raises `UnsupportedFeature`. Some of them take `force=True` to send the frame anyway, at your own risk.

## Low level access
`light.transport` sends raw commands from `govee_h6199_ble.protocol.commands` or raw frames:
```python
from govee_h6199_ble.protocol.commands import GetPact

pact = await light.transport.send_command(GetPact())
raw = await light.transport.exchange_frame(frame, CommandTimeouts())
```

> **Be aware**, if the command is not implemented on the device the call raises `asyncio.TimeoutError`, since no response is received.

## Timeouts
By default, the client uses the following timeouts:
- command send timeout: None
- response receive timeout: 5 seconds

Pass `timeouts=CommandTimeouts(...)` to `GoveeH6199`, or to `transport.send_command`.

## Upgrading from 1.x
Command classes are no longer exported from the package root; use the `GoveeH6199` methods, or import from `govee_h6199_ble.protocol.commands`. The raw send methods moved to `light.transport`. Music sensitivity is now 0-99, and the video mode frame always carries the sound effect fields.

## Credits
Govee for the device and the app.

https://github.com/Obi2000/Govee-H6199-Reverse-Engineering for the details of the protocol.

## Contributing

Both bug reports and pull requests are appreciated.