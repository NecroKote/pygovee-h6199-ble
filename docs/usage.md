# Usage walkthrough

[Getting started](index.md) · [API reference](api.md) · [Connection](connection.md) · [Errors](errors.md)

## Main features

This example connects to the light, reads device information and capabilities, registers a listener, then demonstrates the main features. The second group of actions requires capability flags and is guarded by `caps.*` checks. Without the required capability, a call raises `UnsupportedFeature`, as shown near the end. See the [API reference](api.md) for all available operations.

```python
import asyncio

from bleak import BleakClient, BleakScanner

from govee_h6199_ble import (
    BlackScreenMode,
    GoveeH6199,
    MusicMode,
    StaticColorMode,
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

            # read the firmware, hardware and Wi-Fi chip versions and the protocol identifier once
            info = await light.get_device_info()
            print(f"firmware {info.soft}, hardware {info.hard}")
            print(f"Wi-Fi firmware {info.wifi_soft}, Wi-Fi hardware {info.wifi_hard}")
            print(f"protocol identifier {info.pact}, generation {info.pact and info.pact.generation!r}")

            # read the MAC address of the Wi-Fi chip
            print("mac", await light.get_mac_address())

            # read power, brightness, current mode and the 15 zones sequentially
            print(await light.read_state())

            # --- capabilities -----------------------------------------------

            # read the capabilities for this device (cached after the first call)
            caps = await light.get_capabilities()
            print(caps)

            # --- events -----------------------------------------------------

            # print what the device reports on its own, e.g. changes made from a remote
            remove_listener = light.add_listener(print)

            # --- actions that need no capability flag -----------------------

            # turn the light on
            await light.set_power(True)

            # set the overall brightness, 1-100
            await light.set_brightness(60)

            # paint all zones in one color
            await light.set_static_color((255, 80, 0))

            # use a color temperature; any 2000-9000 K, rounded to the nearest table value
            await light.set_color_temperature(3000)

            # change the color temperature of zone 7 only (zones are 0-14)
            await light.set_color_temperature(6500, zones=[7])

            # set zones 0-6 to red and 8-14 to blue; zone 7 keeps its color
            red, blue = (255, 0, 0), (0, 0, 255)
            await light.set_zone_colors(
                {**{zone: red for zone in range(7)}, **{zone: blue for zone in range(8, 15)}}
            )

            # read back the mode; in the static mode it carries color and temperature per zone
            mode = await light.get_mode(include_zones=True)
            print(mode)
            if isinstance(mode, StaticColorMode):
                print([zone.kelvin for zone in mode.zones or ()])

            # blend the colors of neighbouring zones
            await light.set_gradient(True)
            print("gradient", await light.get_gradient())

            # switch to the music mode, rhythm effect, calm enabled, automatic colors
            await light.set_music_mode(MusicMode.RHYTHM, sensitivity=50, calm=True)

            # switch to the music mode, spectrum effect with a fixed color
            await light.set_music_mode(MusicMode.SPECTRUM, sensitivity=70, color=(0, 255, 0))

            # switch to the music mode, energic effect
            await light.set_music_mode(MusicMode.ENERGIC, sensitivity=70)

            # switch to the music mode, rolling effect with a fixed color
            await light.set_music_mode(MusicMode.ROLLING, sensitivity=70, color=(255, 0, 255))

            # switch to the video mode: full-screen sampling, game mode off, saturation and sound effects
            await light.set_video_mode(
                full_screen=True,
                game_mode=False,
                saturation=70,
                sound_effects=True,
                sound_effects_softness=30,
            )

            # --- actions that depend on the firmware ------------------------

            # needs caps.zone_brightness (not available on protocol generation V1 devices)
            if caps.zone_brightness:
                # set the brightness of zones 0 and 14, 1-100
                await light.set_zone_brightness(40, zones=[0, 14])

                # set the brightness of every zone, 15 values
                await light.set_zone_brightnesses([100 - 5 * zone for zone in range(15)])

            # needs caps.video_brightness or caps.video_segment_brightness
            if caps.video_brightness or caps.video_segment_brightness:
                # set the video mode brightness, the client picks the command the firmware has
                await light.set_video_brightness(70)

            # needs caps.video_segment_brightness (screen-edge brightness; see capabilities)
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

            # needs caps.black_screen (black-screen behavior in video mode)
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

## Interactive check

[`examples/interactive_check.py`](https://github.com/NecroKote/pygovee-h6199-ble/blob/main/examples/interactive_check.py) walks through the main features on a real device. After each change it says what was sent and what to look for, compares with a read-back where the device allows one, and waits for your verdict. It attempts to restore readable settings at the end. Music sensitivity, fixed color and the calm flag cannot be read back, so music mode is restored with default parameters.

Run these commands from a repository checkout after installing the library:

```sh
python examples/interactive_check.py            # all steps
python examples/interactive_check.py --list     # show the steps
python examples/interactive_check.py --only white --only music
```
