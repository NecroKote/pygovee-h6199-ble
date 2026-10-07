"""
Interactive check of a real H6199.

Walks through everything the client can do. After every change it prints what
was sent and what to look for, runs a read-back check where the device allows
one, and waits for your verdict. The original settings are restored at the end
(music sensitivity can't be read, so it comes back at its default).

    python examples/interactive_check.py            # all steps
    python examples/interactive_check.py --list     # show the steps
    python examples/interactive_check.py --only white --only music

Answers: Enter or y = looks right, n = does not, s = skip, r = repeat, q = quit.
"""

import argparse
import asyncio
import sys
import traceback
from dataclasses import dataclass
from typing import Awaitable, Callable

from bleak import BleakClient, BleakScanner

from govee_h6199_ble import (
    BlackScreenMode,
    BlackScreenSetting,
    Capabilities,
    GoveeH6199,
    MusicColorMode,
    MusicMode,
    StaticColorMode,
    UnsupportedFeature,
    VideoColorMode,
    WhiteBalance,
)

BOLD = "\033[1m" if sys.stdout.isatty() else ""
DIM = "\033[2m" if sys.stdout.isatty() else ""
GREEN = "\033[32m" if sys.stdout.isatty() else ""
RED = "\033[31m" if sys.stdout.isatty() else ""
RESET = "\033[0m" if sys.stdout.isatty() else ""

RED_RGB, GREEN_RGB, BLUE_RGB = (255, 0, 0), (0, 255, 0), (0, 0, 255)


@dataclass
class Ctx:
    light: GoveeH6199
    caps: Capabilities
    events: list
    notes: dict


@dataclass
class Step:
    title: str
    doing: str
    look: str
    action: Callable[[Ctx], Awaitable[None]]
    #: returns a description of what did not match, or None
    check: Callable[[Ctx], Awaitable[str | None]] | None = None
    #: name of the `Capabilities` flag the step needs
    needs: str | None = None
    section: str = ""


# --- read-back helpers ------------------------------------------------------


async def expect_static_zones(ctx: Ctx, expected: dict[int, tuple[int, int, int]]):
    mode = await ctx.light.get_mode()
    if not isinstance(mode, StaticColorMode):
        return f"mode is {type(mode).__name__}, expected static color"

    wrong = {
        zone: mode.zones[zone].color
        for zone, color in expected.items()
        if mode.zones[zone].color != color
    }
    return f"zone colors differ: {wrong}" if wrong else None


async def expect_kelvin(ctx: Ctx, kelvin: int, zones=range(15)):
    mode = await ctx.light.get_mode()
    if not isinstance(mode, StaticColorMode):
        return f"mode is {type(mode).__name__}, expected static color"

    wrong = {z: mode.zones[z].kelvin for z in zones if mode.zones[z].kelvin != kelvin}
    return f"zone kelvin differs: {wrong}" if wrong else None


async def expect_music(ctx: Ctx, effect: MusicMode):
    mode = await ctx.light.get_mode()
    if not (isinstance(mode, MusicColorMode) and mode.music_mode == effect):
        return f"mode is {mode}, expected music {effect.name}"


async def expect_video(ctx: Ctx, **fields):
    mode = await ctx.light.get_mode()
    if not isinstance(mode, VideoColorMode):
        return f"mode is {type(mode).__name__}, expected video"

    wrong = {k: getattr(mode, k) for k, v in fields.items() if getattr(mode, k) != v}
    return f"video fields differ: {wrong}" if wrong else None


# --- steps --------------------------------------------------------------------


def build_steps() -> list[Step]:
    steps: list[Step] = []

    def add(section, title, doing, look, action, check=None, needs=None):
        steps.append(Step(title, doing, look, action, check, needs, section))

    # properties
    async def show_info(ctx):
        info = await ctx.light.get_device_info()
        print(f"    firmware {info.soft}, hardware {info.hard}")
        print(f"    wifi firmware {info.wifi_soft}, wifi hardware {info.wifi_hard}")
        print(f"    pact {info.pact}, generation {info.pact and info.pact.generation!r}")
        print(f"    mac {await ctx.light.get_mac_address()}")

    add("Properties", "Device properties", "get_device_info(), get_mac_address()",
        "Versions look plausible for your unit (yours was 1.10.04 / 3.02.01). Wi-Fi versions "
        "are not None. The MAC matches the one on the device label or your router, if you know it.",
        show_info)

    async def show_caps(ctx):
        for name, value in vars(ctx.caps).items():
            print(f"    {name:26} {value}")

    add("Properties", "Capabilities", "get_capabilities()",
        "The flags match what you expect from your hardware. Steps that need a missing "
        "capability are skipped automatically.",
        show_caps)

    async def show_state(ctx):
        state = await ctx.light.read_state()
        print(f"    power {state.power}, brightness {state.brightness}%, mode {state.mode}")
        print(f"    zones {[(z.color, z.brightness) for z in state.zones][:3]} ... (15 total)")

    add("Properties", "Current state", "read_state()",
        "Power and brightness match what the strip does right now.", show_state)

    # power and brightness
    async def power_off(ctx):
        await ctx.light.set_power(False)

    async def power_on(ctx):
        await ctx.light.set_power(True)

    async def check_power(ctx, expected):
        return None if await ctx.light.get_power() == expected else f"power is not {expected}"

    add("Power and brightness", "Power off", "set_power(False)",
        "The whole strip goes dark.", power_off, lambda c: check_power(c, False))
    add("Power and brightness", "Power on", "set_power(True)",
        "The strip lights up again.", power_on, lambda c: check_power(c, True))

    def brightness(percent):
        async def action(ctx):
            await ctx.light.set_brightness(percent)

        async def check(ctx):
            value = await ctx.light.get_brightness()
            return None if abs(value - percent) <= 1 else f"brightness reads {value}"

        return action, check

    for percent, look in (
        (100, "The strip is at its brightest."),
        (20, "The strip is clearly dimmer than a moment ago."),
        (70, "The strip is brighter than at 20%, a bit dimmer than at 100%."),
    ):
        a, c = brightness(percent)
        add("Power and brightness", f"Overall brightness {percent}%",
            f"set_brightness({percent})", look, a, c)

    # static color
    def static(color, name):
        async def action(ctx):
            await ctx.light.set_static_color(color)

        return action, lambda c: expect_static_zones(c, {z: color for z in range(15)})

    for color, name in ((RED_RGB, "red"), (GREEN_RGB, "green"), (BLUE_RGB, "blue")):
        a, c = static(color, name)
        add("Static color", f"All zones {name}", f"set_static_color({color})",
            f"Every zone of the strip shows solid {name}.", a, c)

    async def left_right(ctx):
        await ctx.light.set_zone_colors(
            {**{z: RED_RGB for z in range(7)}, **{z: BLUE_RGB for z in range(8, 15)}}
        )

    add("Static color", "Per-zone colors: zones 0-6 red, 8-14 blue",
        "set_zone_colors({0-6: red, 8-14: blue})",
        "One half of the strip is red and the other half blue, with the middle zone (7) "
        "keeping the previous color. Which half is which depends on how the strip is mounted; "
        "note the order, the next steps use the same zone numbers.",
        left_right,
        lambda c: expect_static_zones(
            c, {**{z: RED_RGB for z in range(7)}, **{z: BLUE_RGB for z in range(8, 15)}}
        ))

    async def single_zone(ctx):
        await ctx.light.set_zone_colors({7: GREEN_RGB})

    add("Static color", "Single zone: zone 7 green", "set_zone_colors({7: green})",
        "Only the middle zone changes to green. The red and blue halves stay as they were.",
        single_zone, lambda c: expect_static_zones(c, {7: GREEN_RGB, 0: RED_RGB, 14: BLUE_RGB}))

    async def gradient_on(ctx):
        await ctx.light.set_gradient(True)

    async def gradient_off(ctx):
        await ctx.light.set_gradient(False)

    async def check_gradient(ctx, expected):
        return None if await ctx.light.get_gradient() == expected else "gradient read-back differs"

    add("Static color", "Gradient on", "set_gradient(True)",
        "The edge between the red and blue halves (and around the green zone) turns into a "
        "smooth blend instead of a hard step.",
        gradient_on, lambda c: check_gradient(c, True))
    add("Static color", "Gradient off", "set_gradient(False)",
        "Colors have hard edges between zones again.",
        gradient_off, lambda c: check_gradient(c, False))

    # color temperature
    def kelvin(value, look):
        async def action(ctx):
            sent = await ctx.light.set_color_temperature(value)
            print(f"    sent {sent} K")

        add("Color temperature", f"{value} K", f"set_color_temperature({value})", look,
            action, lambda c: expect_kelvin(c, value))

    kelvin(2000, "Very warm, orange-ish white across the whole strip.")
    kelvin(4000, "Warm neutral white, less orange than 2000 K.")
    kelvin(6500, "Neutral to slightly cool white.")
    kelvin(9000, "Cool, bluish white.")

    async def snapped(ctx):
        sent = await ctx.light.set_color_temperature(6700)
        print(f"    asked for 6700 K, sent {sent} K")

    add("Color temperature", "Value without a table entry: 6700 K",
        "set_color_temperature(6700)",
        "Looks the same as the 6500 K step above (the value is rounded, nothing goes black).",
        snapped, lambda c: expect_kelvin(c, 6500))

    async def kelvin_zone(ctx):
        await ctx.light.set_color_temperature(2000, zones=[0, 1, 2])
        await ctx.light.set_color_temperature(9000, zones=[12, 13, 14])

    async def check_kelvin_zone(ctx):
        return (await expect_kelvin(ctx, 2000, [0, 1, 2])
                or await expect_kelvin(ctx, 9000, [12, 13, 14]))

    add("Color temperature", "Per-zone temperature: zones 0-2 at 2000 K, 12-14 at 9000 K",
        "set_color_temperature(2000, zones=[0,1,2]); set_color_temperature(9000, zones=[12,13,14])",
        "The three zones at one end are warm orange-white, the three at the other end are cool "
        "blue-white, the zones in between keep the 6500 K white.",
        kelvin_zone, check_kelvin_zone)

    # zone brightness
    async def zones_base(ctx):
        await ctx.light.set_static_color((255, 255, 255))
        await ctx.light.set_zone_brightness(100)

    async def zone_dim(ctx):
        await ctx.light.set_zone_brightness(20, zones=[0, 14])

    async def check_zone_dim(ctx):
        zones = await ctx.light.get_zone_states()
        if (zones[0].brightness, zones[14].brightness, zones[7].brightness) != (20, 20, 100):
            return f"brightness reads {[z.brightness for z in zones]}"

    add("Zone brightness", "Reset to white at full brightness",
        "set_static_color(white); set_zone_brightness(100)",
        "The whole strip is evenly white and bright.", zones_base, needs="zone_brightness")
    add("Zone brightness", "Dim the end zones: 0 and 14 to 20%",
        "set_zone_brightness(20, zones=[0, 14])",
        "Only the two zones at the opposite ends of the strip are dimmer, the rest is unchanged.",
        zone_dim, check_zone_dim, needs="zone_brightness")

    async def zone_ramp(ctx):
        await ctx.light.set_zone_brightnesses([100 - 6 * z for z in range(15)])

    async def check_ramp(ctx):
        zones = await ctx.light.get_zone_states()
        expected = [100 - 6 * z for z in range(15)]
        got = [z.brightness for z in zones]
        return None if got == expected else f"brightness reads {got}"

    add("Zone brightness", "Brightness ramp over all 15 zones",
        "set_zone_brightnesses([100, 94, 88, ... 16])",
        "Brightness falls off evenly from zone 0 (brightest) to zone 14 (dimmest).",
        zone_ramp, check_ramp, needs="zone_brightness")

    # music
    music_hint = (" Play music (or clap) close to the device: the lights should react to the "
                  "sound and calm down when it stops.")

    def music(effect, title, doing, look, **kwargs):
        async def action(ctx):
            await ctx.light.set_music_mode(effect, **kwargs)

        add("Music mode", title, doing, look + music_hint, action,
            lambda c: expect_music(c, effect))

    music(MusicMode.RYTHM, "Rhythm, soft, automatic colors",
          "set_music_mode(RYTHM, sensitivity=70, calm=True)",
          "Gentle pulsing to the beat, colors change on their own.", sensitivity=70, calm=True)
    music(MusicMode.RYTHM, "Rhythm, dynamic, fixed color",
          "set_music_mode(RYTHM, sensitivity=70, calm=False, color=green)",
          "Stronger reaction than the soft variant, in green only.",
          sensitivity=70, calm=False, color=GREEN_RGB)
    music(MusicMode.SPECTRUM, "Spectrum, automatic colors",
          "set_music_mode(SPECTRUM, sensitivity=70)",
          "Colors follow the frequency spectrum, they change on their own.", sensitivity=70)
    music(MusicMode.SPECTRUM, "Spectrum, fixed color",
          "set_music_mode(SPECTRUM, sensitivity=70, color=blue)",
          "The spectrum effect uses blue only.", sensitivity=70, color=BLUE_RGB)
    music(MusicMode.ENERGIC, "Energic",
          "set_music_mode(ENERGIC, sensitivity=70)",
          "Fast, energetic flashing in colors the device picks.", sensitivity=70)
    music(MusicMode.ROLLING, "Rolling, automatic colors",
          "set_music_mode(ROLLING, sensitivity=70)",
          "Colors roll along the strip, they change on their own.", sensitivity=70)
    music(MusicMode.ROLLING, "Rolling, fixed color",
          "set_music_mode(ROLLING, sensitivity=70, color=magenta)",
          "The rolling effect uses magenta only.", sensitivity=70, color=(255, 0, 255))

    async def sens_low(ctx):
        await ctx.light.set_music_mode(MusicMode.RYTHM, sensitivity=5)

    async def sens_high(ctx):
        await ctx.light.set_music_mode(MusicMode.RYTHM, sensitivity=99)

    add("Music mode", "Sensitivity 5", "set_music_mode(RYTHM, sensitivity=5)",
        "With the same music the lights react only weakly." + music_hint, sens_low,
        lambda c: expect_music(c, MusicMode.RYTHM))
    add("Music mode", "Sensitivity 99", "set_music_mode(RYTHM, sensitivity=99)",
        "With the same music the lights react much more than at 5." + music_hint, sens_high,
        lambda c: expect_music(c, MusicMode.RYTHM))

    # video mode
    video_hint = (" Show a colorful picture on the TV the device is mounted on; the lights "
                  "should follow the colors of the picture.")

    def video(title, doing, look, expect, **kwargs):
        async def action(ctx):
            await ctx.light.set_video_mode(**kwargs)

        add("Video mode", title, doing, look + video_hint, action,
            lambda c: expect_video(c, **expect))

    video("Whole screen, movie, saturation 50",
          "set_video_mode(full_screen=True, game_mode=False, saturation=50)",
          "The lights follow the picture, in natural colors.",
          dict(full_screen=True, game_mode=False, saturation=50, sound_effects=False),
          full_screen=True, game_mode=False, saturation=50)
    video("Partial screen",
          "set_video_mode(full_screen=False, game_mode=False, saturation=50)",
          "The lights now sample part of the picture instead of the whole screen; "
          "colors per zone may differ from the previous step.",
          dict(full_screen=False, game_mode=False),
          full_screen=False, game_mode=False, saturation=50)
    video("Game mode",
          "set_video_mode(full_screen=True, game_mode=True, saturation=50)",
          "Lights react faster to changes in the picture than in movie mode.",
          dict(full_screen=True, game_mode=True),
          full_screen=True, game_mode=True, saturation=50)
    video("Saturation 100",
          "set_video_mode(full_screen=True, game_mode=False, saturation=100)",
          "Colors are visibly more vivid than at 50.",
          dict(saturation=100, game_mode=False, full_screen=True),
          full_screen=True, game_mode=False, saturation=100)
    video("Saturation 10",
          "set_video_mode(full_screen=True, game_mode=False, saturation=10)",
          "Colors are washed out, close to white.",
          dict(saturation=10),
          full_screen=True, game_mode=False, saturation=10)
    video("Sound effects on, softness 80",
          "set_video_mode(saturation=70, sound_effects=True, sound_effects_softness=80)",
          "With music playing, the lights also pulse with the sound, softly.",
          dict(saturation=70, sound_effects=True, sound_effects_softness=80),
          full_screen=True, game_mode=False, saturation=70,
          sound_effects=True, sound_effects_softness=80)
    video("Sound effects on, softness 10",
          "set_video_mode(saturation=70, sound_effects=True, sound_effects_softness=10)",
          "With music playing, the sound reaction is sharper than at softness 80.",
          dict(sound_effects=True, sound_effects_softness=10),
          full_screen=True, game_mode=False, saturation=70,
          sound_effects=True, sound_effects_softness=10)
    video("Sound effects off", "set_video_mode(saturation=70, sound_effects=False)",
          "The lights follow only the picture again, no pulsing with the sound.",
          dict(sound_effects=False),
          full_screen=True, game_mode=False, saturation=70, sound_effects=False)

    async def vb_low(ctx):
        await ctx.light.set_video_brightness(20)

    async def vb_high(ctx):
        await ctx.light.set_video_brightness(100)

    for fn, value, look in (
        (vb_low, 20, "The lights are much dimmer than before."),
        (vb_high, 100, "The lights are at full video brightness again."),
    ):
        add("Video mode", f"Video brightness {value}", f"set_video_brightness({value})",
            look + video_hint, fn)

    async def edges_dim_bottom(ctx):
        await ctx.light.set_video_edge_brightness(left=100, top=100, right=100, bottom=10)

    async def check_edges(ctx):
        edges = await ctx.light.get_video_edge_brightness()
        return None if tuple(edges) == (100, 100, 100, 10) else f"edges read {tuple(edges)}"

    add("Video mode", "Screen edges: bottom to 10%",
        "set_video_edge_brightness(left=100, top=100, right=100, bottom=10)",
        "The lights on the bottom edge of the TV are much dimmer than the left, top and right "
        "edges." + video_hint, edges_dim_bottom, check_edges, needs="video_segment_brightness")

    async def edges_all(ctx):
        await ctx.light.set_video_edge_brightness(left=100, top=100, right=100, bottom=100)

    add("Video mode", "Screen edges: all at 100%",
        "set_video_edge_brightness(left=100, top=100, right=100, bottom=100)",
        "All four edges are equally bright again." + video_hint,
        edges_all, None, needs="video_segment_brightness")

    # white balance
    wb_hint = (" Show a plain grey or white picture on the TV and compare with the previous "
               "step. Across the 20 steps the red gain rises from 7 to 21 and the blue gain "
               "falls from 10 to 5, so the tint moves from cool to warm.")

    def wb(step, look, pair):
        async def action(ctx):
            await ctx.light.set_white_balance(step)

        async def check(ctx):
            state = await ctx.light.get_white_balance()
            ok = state.current.step == step and not state.current.auto
            return None if ok else f"reads {state.current}"

        add("White balance", f"Step {step} (red {pair[0]}, blue {pair[1]})",
            f"set_white_balance({step})", look + wb_hint, action, check, needs="white_balance")

    wb(1, "The light is on the cool, bluish side.", (7, 10))
    wb(20, "The light is clearly warmer / redder than at step 1.", (21, 5))
    wb(5, "Between the two: warmer than step 1, cooler than step 20.", (10, 6))

    async def wb_auto(ctx):
        await ctx.light.set_white_balance_auto()

    async def wb_auto_check(ctx):
        state = await ctx.light.get_white_balance()
        return None if state.current.auto else f"reads {state.current}"

    add("White balance", "Automatic", "set_white_balance_auto()",
        "The device picks the white balance itself; the tint may change." + wb_hint,
        wb_auto, wb_auto_check, needs="white_balance")

    async def wb_reset(ctx):
        await ctx.light.reset_white_balance()

    async def wb_reset_check(ctx):
        state = await ctx.light.get_white_balance()
        c = state.current
        return None if (c.red, c.blue) == state.default else f"reads {c}, default {state.default}"

    add("White balance", "Reset to the device default", "reset_white_balance()",
        "The tint settles at the device's default (red 16, blue 3 on a tested unit)." + wb_hint,
        wb_reset, wb_reset_check, needs="white_balance")

    # black screen
    async def black_low(ctx):
        await ctx.light.set_black_screen(
            BlackScreenSetting(True, BlackScreenMode.LOW_BRIGHTNESS, 5, 300)
        )

    async def check_black_low(ctx):
        s = await ctx.light.get_black_screen()
        ok = (s.enabled, s.mode, s.low_brightness_seconds) == (True, BlackScreenMode.LOW_BRIGHTNESS, 5)
        return None if ok else f"reads {s}"

    add("Black screen", "Low brightness after 5 s", "set_black_screen(on, LOW_BRIGHTNESS, 5 s, 300 s)",
        "Nothing changes right now. To test the behaviour, put a completely black picture on the "
        "TV in video mode: after about 5 seconds the lights should drop to a low brightness. "
        "Answer s if you can't show a black picture.",
        black_low, check_black_low, needs="black_screen")

    async def black_same(ctx):
        await ctx.light.update_black_screen(mode=BlackScreenMode.SAME_TONE, same_tone_seconds=120)

    async def check_black_same(ctx):
        s = await ctx.light.get_black_screen()
        ok = (s.mode, s.same_tone_seconds, s.low_brightness_seconds) == (BlackScreenMode.SAME_TONE, 120, 5)
        return None if ok else f"reads {s}"

    add("Black screen", "Same tone for 120 s", "update_black_screen(mode=SAME_TONE, same_tone_seconds=120)",
        "Nothing changes right now. With a black picture on the TV the lights should keep the "
        "last color for about 2 minutes. The 5 s low brightness value from the previous step "
        "must be kept (see the read-back).",
        black_same, check_black_same, needs="black_screen")

    async def black_off(ctx):
        await ctx.light.update_black_screen(enabled=False)

    async def check_black_off(ctx):
        s = await ctx.light.get_black_screen()
        return None if not s.enabled else f"reads {s}"

    add("Black screen", "Disabled", "update_black_screen(enabled=False)",
        "Nothing changes right now. With a black picture the lights follow it (go dark).",
        black_off, check_black_off, needs="black_screen")

    # gating and events
    async def gating(ctx):
        ctx.notes["raised"] = False
        try:
            await ctx.light.set_video_edge_brightness(50, 50, 50, 50)
        except UnsupportedFeature as error:
            ctx.notes["raised"] = True
            print(f"    raised UnsupportedFeature: {error}")
            return

        print("    no error: the device supports edge brightness")

    async def check_gating(ctx):
        if ctx.notes["raised"] == ctx.caps.video_segment_brightness:
            return "raised / not raised does not match the video_segment_brightness capability"

    add("Gating", "Missing capability raises", "set_video_edge_brightness(50, 50, 50, 50)",
        "If your capabilities say video_segment_brightness is False the call raises "
        "UnsupportedFeature (printed below). If it is True the call works and the bottom edge "
        "brightness changes. Either way the printed line must match the capabilities.",
        gating, check_gating)

    async def events(ctx):
        ctx.events.clear()
        print("    listening for 20 s. Change something with another controller now "
              "(remote, phone: brightness or power).")
        await asyncio.sleep(20)
        print(f"    events received: {ctx.events or 'none'}")

    add("Events", "Device-initiated events", "add_listener(print), wait 20 s",
        "Change the brightness or power with another controller during the wait. Events appear "
        "above. Answer s if you can't (none have been seen from a device yet).", events)

    return steps


# --- runner -------------------------------------------------------------------


async def ask(prompt: str) -> str:
    try:
        return (await asyncio.to_thread(input, prompt)).strip().lower()
    except EOFError:
        return "q"


async def run_steps(ctx: Ctx, steps: list[Step]) -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []
    section = None

    for number, step in enumerate(steps, 1):
        if step.needs and not getattr(ctx.caps, step.needs):
            print(f"{DIM}[{number}/{len(steps)}] {step.title}: skipped, "
                  f"capability {step.needs} is False{RESET}")
            results.append((step.title, "SKIP", f"needs {step.needs}"))
            continue

        if step.section != section:
            section = step.section
            print(f"\n{BOLD}=== {section} ==={RESET}")

        while True:
            print(f"\n{BOLD}[{number}/{len(steps)}] {step.title}{RESET}")
            print(f"  Doing:     {step.doing}")
            print(f"  Look for:  {step.look}")

            detail = ""
            try:
                await step.action(ctx)
                await asyncio.sleep(0.8)
                mismatch = await step.check(ctx) if step.check else None
            except UnsupportedFeature as error:
                print(f"  {RED}Refused:{RESET} {error}")
                results.append((step.title, "SKIP", str(error)))
                break
            except Exception:
                traceback.print_exc()
                results.append((step.title, "ERROR", "exception"))
                break

            if step.check:
                if mismatch:
                    detail = f"read-back: {mismatch}"
                    print(f"  Read-back: {RED}MISMATCH{RESET} {mismatch}")
                else:
                    print(f"  Read-back: {GREEN}OK{RESET}")
            else:
                print(f"  Read-back: {DIM}not available for this step{RESET}")

            answer = await ask("  Does it look as described? "
                               "[Enter=yes, n=no, s=skip, r=repeat, q=quit] ")
            if answer == "r":
                continue
            if answer == "q":
                results.append((step.title, "SKIP", "quit"))
                return results

            if answer in ("", "y", "yes"):
                verdict = "FAIL" if mismatch else "PASS"
                if mismatch:
                    detail = detail or "read-back mismatch"
            elif answer == "s":
                verdict = "SKIP"
            else:
                verdict = "FAIL"
                note = await ask("  What did you see instead? (optional) ")
                detail = f"{detail}; saw: {note}" if note else detail

            results.append((step.title, verdict, detail))
            break

    return results


async def restore(light: GoveeH6199, caps: Capabilities, saved: dict):
    print(f"\n{BOLD}Restoring the original settings{RESET}")
    state = saved["state"]

    async def attempt(label, coroutine):
        try:
            await coroutine
        except Exception as error:
            print(f"  could not restore {label}: {error}")

    await attempt("zone colors", light.set_zone_colors([z.color for z in state.zones]))
    if caps.zone_brightness:
        await attempt("zone brightness",
                      light.set_zone_brightnesses([z.brightness for z in state.zones]))
    await attempt("gradient", light.set_gradient(saved["gradient"]))

    mode = state.mode
    if isinstance(mode, VideoColorMode):
        await attempt("video mode", light.set_video_mode(
            mode.full_screen, mode.game_mode, max(1, mode.saturation),
            mode.sound_effects, max(1, mode.sound_effects_softness)))
    elif isinstance(mode, MusicColorMode):
        print("  music sensitivity and colors can't be read, restoring the effect at defaults")
        await attempt("music mode", light.set_music_mode(mode.music_mode))

    if saved.get("white_balance"):
        await attempt("white balance", light.set_white_balance_raw(saved["white_balance"]))
    if saved.get("edges"):
        await attempt("edge brightness", light.set_video_edge_brightness(*saved["edges"]))
    if saved.get("black_screen"):
        await attempt("black screen", light.set_black_screen(saved["black_screen"]))

    await attempt("brightness", light.set_brightness(max(1, state.brightness)))
    await attempt("power", light.set_power(state.power))
    print("  done")


async def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--list", action="store_true", help="list the steps and exit")
    parser.add_argument("--only", action="append", default=[],
                        help="run only steps whose section or title contains this text")
    parser.add_argument("--name", default="Govee_H6199", help="device name prefix to scan for")
    parser.add_argument("--address", help="connect to this address (macOS: UUID) instead of scanning")
    parser.add_argument("--no-restore", action="store_true", help="leave the final state as is")
    args = parser.parse_args()

    steps = build_steps()
    if args.only:
        needles = [n.lower() for n in args.only]
        steps = [s for s in steps if any(n in (s.section + " " + s.title).lower() for n in needles)]

    if args.list:
        section = None
        for number, step in enumerate(steps, 1):
            if step.section != section:
                section = step.section
                print(f"\n{section}")
            gate = f"  (needs {step.needs})" if step.needs else ""
            print(f"  {number:2}. {step.title}{gate}")
        return 0

    if not steps:
        print("no steps match")
        return 1

    target = args.address or await BleakScanner.find_device_by_filter(
        lambda d, a: bool((a.local_name or d.name or "").startswith(args.name)), timeout=30
    )
    if target is None:
        print("no device found. Close other apps connected to it and try again.")
        return 1

    async with BleakClient(target) as client:
        async with GoveeH6199(client) as light:
            caps = await light.get_capabilities()
            ctx = Ctx(light, caps, [], {})
            light.add_listener(ctx.events.append)

            state = await light.read_state()
            saved = {"state": state, "gradient": await light.get_gradient()}
            if caps.white_balance:
                saved["white_balance"] = (await light.get_white_balance()).current
            if caps.video_segment_brightness:
                saved["edges"] = tuple(await light.get_video_edge_brightness())
            if caps.black_screen:
                saved["black_screen"] = await light.get_black_screen()

            print(f"{BOLD}Interactive check of {len(steps)} steps.{RESET} "
                  "The strip will change a lot. Original settings are restored at the end.")

            try:
                results = await run_steps(ctx, steps)
            finally:
                if not args.no_restore:
                    await restore(light, caps, saved)

    print(f"\n{BOLD}Summary{RESET}")
    for title, verdict, detail in results:
        color = {"PASS": GREEN, "FAIL": RED, "ERROR": RED}.get(verdict, DIM)
        print(f"  {color}{verdict:5}{RESET} {title}" + (f"  ({detail})" if detail else ""))

    counts = {v: sum(1 for _, x, _ in results if x == v) for v in ("PASS", "FAIL", "ERROR", "SKIP")}
    print("\n  " + ", ".join(f"{n} {v.lower()}" for v, n in counts.items()))
    return 1 if counts["FAIL"] or counts["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
