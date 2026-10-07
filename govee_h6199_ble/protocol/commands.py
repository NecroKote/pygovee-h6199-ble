import re
from typing import Iterable, Sequence

from .colortemp import MIN_KELVIN, kelvin_for_color, tint_for_kelvin
from .base import Command, CommandPayload, CommandWithParser
from .const import (
    ZONE_COUNT,
    ZONE_GROUP_SIZE,
    ColorKind,
    ColorMode,
    MusicMode,
    PacketHeader,
    PacketType,
    VideoParam,
)
from ..model import (
    LOW_BRIGHTNESS_SECONDS,
    SAME_TONE_SECONDS,
    BlackScreenMode,
    BlackScreenSetting,
    EdgeBrightness,
    Modes,
    Pact,
    WHITE_BALANCE_MAX,
    WhiteBalance,
    WhiteBalanceState,
    MusicColorMode,
    RGBColor,
    StaticColorMode,
    UnknownColorMode,
    VideoColorMode,
    ZoneState,
)
from .packet import zone_mask


class GetStatus(CommandWithParser[bytes]):
    """
    Get the status of the specific domain

    Equivalent to: calling `command_with_reply` with `PacketHeader.STATUS`
    and `domain` as the first byte
    """

    def __init__(self, domain: int, payload: list[int] | None = None):
        self._domain = domain
        self._payload = payload or []

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, self._domain, self._payload)

    def parse_response(self, response):
        return response


class GetPowerState(CommandWithParser[bool]):
    """Get the power state of the device"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.POWER, [])

    def parse_response(self, response: bytes):
        return bool(response[0])


class PowerOn(Command):
    """Turn on the device"""

    def payload(self):
        return CommandPayload(PacketHeader.COMMAND, PacketType.POWER, [0x01])


class PowerOff(Command):
    """Turn off the device"""

    def payload(self):
        return CommandPayload(PacketHeader.COMMAND, PacketType.POWER, [0x00])


class GetFirmwareVersion(CommandWithParser[str]):
    """Get the firmware version of the device"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.FW, [])

    def parse_response(self, response: bytes):
        return str(response[0:7], encoding="ascii")


class GetHardwareVersion(CommandWithParser[str]):
    """Get the hardware version of the device"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.HW, [0x03])

    def parse_response(self, response: bytes):
        return str(response[1:8], encoding="ascii")


class GetPact(CommandWithParser[Pact]):
    """
    Get the protocol id (pact) of the device

    `Pact.generation` tells V1-V4: V1 uses the legacy color sub-mode, V2+
    the one used by this library.
    """

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.PACT, [])

    def parse_response(self, response: bytes):
        return Pact((response[0] << 8) | response[1], response[2])


def _parse_version(response: bytes) -> str:
    # ASCII text, NUL-terminated
    match = re.search(rb"\d+\.\d+\.\d+", response)
    if match is None:
        raise ValueError(f"no version in response {response.hex()}")

    return match.group().decode("ascii")


class GetWifiFirmwareVersion(CommandWithParser[str]):
    """Get the firmware version of the device's WiFi chip"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.WIFI_SW, [])

    def parse_response(self, response: bytes):
        return _parse_version(response)


class GetWifiHardwareVersion(CommandWithParser[str]):
    """Get the hardware version of the device's WiFi chip"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.WIFI_HW, [])

    def parse_response(self, response: bytes):
        return _parse_version(response)


class GetMacAddress(CommandWithParser[str]):
    """Get the MAC address of the device's WiFi chip"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.MAC, [])

    def parse_response(self, response: bytes):
        raw = response[:6]
        return ":".join((f"{x:02x}" for x in raw))


class SetBrightness(Command):
    """
    Set the brightness of the device

    :param percent: The brightness percentage (1-100)
    :param scale: Device maximum: 100, or 254 for pact V1
    """

    def __init__(self, percent: int, scale: int = 100):
        if not 1 <= percent <= 100:
            raise ValueError("value must be 1-100")

        self._value = max(1, round(percent * scale / 100))

    def payload(self):
        return CommandPayload(
            PacketHeader.COMMAND, PacketType.BRIGHTNESS, [self._value]
        )


class GetBrightness(CommandWithParser[int]):
    """
    Get the brightness of the device in percent

    :param scale: Device maximum: 100, or 254 for pact V1
    """

    def __init__(self, scale: int = 100):
        self._scale = scale

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.BRIGHTNESS, [])

    def parse_response(self, response):
        return min(100, round(response[0] * 100 / self._scale))


class GetColorMode(CommandWithParser[Modes]):
    """
    Get the current mode the device is in

    A static mode reply carries only the kind of the last frame. The colors
    are read separately, see `GetZoneGroup`.
    """

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.COLOR, [0x01])

    def parse_response(self, response):
        try:
            mode = ColorMode(response[0])
        except ValueError:
            return UnknownColorMode(response[0])

        match mode:
            case ColorMode.VIDEO:
                return VideoColorMode(
                    full_screen=bool(response[1]),
                    game_mode=bool(response[2]),
                    saturation=response[3],
                    sound_effects=bool(response[4]),
                    sound_effects_softness=response[5],
                    brightness=response[6],
                )

            case ColorMode.MUSIC:
                try:
                    return MusicColorMode(MusicMode(response[1]))
                except ValueError:
                    return UnknownColorMode(response[0])

            case ColorMode.STATIC:
                try:
                    return StaticColorMode(ColorKind(response[1]))
                except ValueError:
                    return StaticColorMode()

            case ColorMode.STATIC_V1:
                return StaticColorMode()

        return UnknownColorMode(response[0])

        match mode:
            case ColorMode.VIDEO:
                return VideoColorMode(
                    full_screen=bool(response[1]),
                    game_mode=bool(response[2]),
                    saturation=response[3],
                    sound_effects=bool(response[4]),
                    sound_effects_softness=response[5],
                    brightness=response[6],
                )

            case ColorMode.MUSIC:
                try:
                    return MusicColorMode(MusicMode(response[1]))
                except ValueError:
                    return UnknownColorMode(response[0])

            case ColorMode.STATIC:
                # HINT: the current fw version (1.10.04) doesn't seem to return the static color
                return StaticColorMode()

        return UnknownColorMode(response[0])


class SetStaticColor(Command):
    """Switch the device in the Static Color mode"""

    def __init__(
        self,
        rgb_color: RGBColor,
    ):
        self._color = rgb_color

    def payload(self):
        return SetZoneColor(self._color).payload()


class SetMusicModeRythm(Command):
    """Switch the device in the Music mode with Rythm effect"""

    def __init__(
        self,
        calm: bool = True,
        sensitivity: int = 99,
        rgb_color: RGBColor | None = None,
    ):
        if not 0 <= sensitivity <= 99:
            raise ValueError("sensitivity must be 0-99")

        self._calm = calm
        self._color = rgb_color
        self._sensitivity = sensitivity

    def payload(self):
        pkt = [ColorMode.MUSIC, MusicMode.RYTHM, self._sensitivity, int(self._calm)]

        if self._color:
            r, g, b = self._color
            pkt += [0x01, r, g, b]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetMusicModeEnergic(Command):
    """Switch the device in the Music mode with Energic effect"""

    def __init__(self, sensitivity: int = 99):
        if not 0 <= sensitivity <= 99:
            raise ValueError("sensitivity must be 0-99")

        self._sensitivity = sensitivity

    def payload(self):
        return CommandPayload(
            PacketHeader.COMMAND,
            PacketType.COLOR,
            [ColorMode.MUSIC, MusicMode.ENERGIC, self._sensitivity],
        )


class SetMusicModeSpectrum(Command):
    """Switch the device in the Music mode with Spectrum effect"""

    def __init__(
        self,
        sensitivity: int = 99,
        rgb_color: RGBColor | None = None,
    ):
        if not 0 <= sensitivity <= 99:
            raise ValueError("sensitivity must be 0-99")

        self._color = rgb_color
        self._sensitivity = sensitivity

    def payload(self):
        pkt = [ColorMode.MUSIC, MusicMode.SPECTRUM, self._sensitivity, 0x00]

        if self._color:
            r, g, b = self._color
            pkt += [0x01, r, g, b]

        return CommandPayload(
            PacketHeader.COMMAND,
            PacketType.COLOR,
            pkt,
        )


class SetMusicModeRolling(Command):
    """Switch the device in the Music mode with Rolling effect"""

    def __init__(
        self,
        sensitivity: int = 99,
        rgb_color: RGBColor | None = None,
    ):
        if not 0 <= sensitivity <= 99:
            raise ValueError("sensitivity must be 0-99")

        self._color = rgb_color
        self._sensitivity = sensitivity

    def payload(self):
        pkt = [ColorMode.MUSIC, MusicMode.ROLLING, self._sensitivity, 0x00]

        if self._color:
            r, g, b = self._color
            pkt += [0x01, r, g, b]

        return CommandPayload(
            PacketHeader.COMMAND,
            PacketType.COLOR,
            pkt,
        )


class SetVideoMode(Command):
    """
    Switch the device in the Video mode a.k.a Camera mode

    :param saturation: 1-100
    :param sound_effects_softness: 1-100
    :param brightness: 1-100, relative brightness. Only honored by firmware that
        carries it in this frame (Telink); leave `None` otherwise
    """

    def __init__(
        self,
        full_screen: bool = True,
        game_mode: bool = False,
        saturation: int = 50,
        sound_effects: bool = False,
        sound_effects_softness: int = 50,
        brightness: int | None = None,
    ):
        if not 1 <= saturation <= 100:
            raise ValueError("saturation must be 1-100")

        if not 1 <= sound_effects_softness <= 100:
            raise ValueError("sound_effects_softness must be 1-100")

        if brightness is not None and not 1 <= brightness <= 100:
            raise ValueError("brightness must be 1-100")

        self._full_screen = full_screen
        self._saturation = saturation
        self._game_mode = game_mode
        self._sound_effects = sound_effects
        self._sound_effects_softness = sound_effects_softness
        self._brightness = brightness

    def payload(self):
        pkt = [
            ColorMode.VIDEO,
            int(self._full_screen),
            int(self._game_mode),
            self._saturation,
            int(self._sound_effects),
            self._sound_effects_softness,
        ]

        if self._brightness is not None:
            pkt.append(self._brightness)

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


def _check_percent(name: str, value: int):
    if not 1 <= value <= 100:
        raise ValueError(f"{name} must be 1-100")


class SetZoneColor(Command):
    """
    Switch the device in the Static Color mode and set color of the given zones

    Zones are numbered 0-14. Send several commands with different zones to
    paint different colors; the zones that are not mentioned keep their color.

    :param rgb_color: (r, g, b), 0-255 each
    :param zones: zones to paint, `None` for all of them
    """

    def __init__(self, rgb_color: RGBColor, zones: Iterable[int] | None = None):
        if not all(0 <= c <= 255 for c in rgb_color):
            raise ValueError("color components must be 0-255")

        self._color = rgb_color
        self._mask = zone_mask(zones)

    def payload(self):
        r, g, b = self._color
        # kelvin and tint are zeroed for a plain color
        pkt = [ColorMode.STATIC, ColorKind.COLOR, r, g, b] + ([0x00] * 5)
        pkt += self._mask

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetZoneColorTemperature(Command):
    """
    Switch the device in the Static Color mode with a color temperature

    :param kelvin: a value of the color table (see `COLOR_TEMPERATURES`),
        `nearest_color_temperature` rounds any value to one
    :param zones: zones to change, `None` for all of them
    """

    def __init__(self, kelvin: int, zones: Iterable[int] | None = None):
        self._kelvin = kelvin
        self._tint = tint_for_kelvin(kelvin)
        self._mask = zone_mask(zones)

    def payload(self):
        pkt = [ColorMode.STATIC, ColorKind.COLOR, 0xFF, 0xFF, 0xFF]
        pkt += [*self._kelvin.to_bytes(2, "big"), *self._tint, *self._mask]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetZoneColorTemperatureV1(SetZoneColorTemperature):
    """Legacy (pact V1) variant of `SetZoneColorTemperature`, sub-mode 0x0B"""

    def payload(self):
        pkt = [ColorMode.STATIC_V1, *self._tint]
        pkt += [*self._kelvin.to_bytes(2, "big"), *self._mask]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetZoneBrightness(Command):
    """
    Set brightness of the given zones

    Brightness frames should be sent at most once per 100 ms when sending
    them continuously, e.g. while dragging a slider.

    :param percent: 1-100
    :param zones: zones to change, `None` for all of them
    """

    def __init__(self, percent: int, zones: Iterable[int] | None = None):
        _check_percent("percent", percent)

        self._value = percent
        self._mask = zone_mask(zones)

    def payload(self):
        pkt = [ColorMode.STATIC, ColorKind.ZONE_BRIGHTNESS, self._value, *self._mask]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetZoneBrightnessList(Command):
    """
    Set brightness of every zone at once

    :param percents: exactly 15 values, 1-100 each
    """

    def __init__(self, percents: Sequence[int]):
        if len(percents) != ZONE_COUNT:
            raise ValueError(f"expected {ZONE_COUNT} values, got {len(percents)}")

        for value in percents:
            _check_percent("percents item", value)

        self._values = list(percents)

    def payload(self):
        pkt = [ColorMode.STATIC, ColorKind.ZONE_BRIGHTNESS_LIST, *self._values]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class GetZoneGroup(CommandWithParser[list[ZoneState]]):
    """
    Get color and brightness of a group of 4 zones

    :param group: 1-4. Group 4 holds zones 12-14 only.

    Use `GoveeH6199.get_zone_states` to read all zones at once.
    """

    _command = PacketType.ZONE_COLORS
    _stride = 4  # [brightness, r, g, b]

    def __init__(self, group: int):
        if not 1 <= group <= -(-ZONE_COUNT // ZONE_GROUP_SIZE):
            raise ValueError("group must be 1-4")

        self._group = group

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, self._command, [self._group])

    def parse_response(self, response: bytes):
        first = (response[0] - 1) * ZONE_GROUP_SIZE
        zones = []
        for slot in range(ZONE_GROUP_SIZE):
            if first + slot >= ZONE_COUNT:
                break  # padding slot

            raw = response[1 + slot * self._stride : 1 + (slot + 1) * self._stride]
            zones.append(self._zone(raw))

        return zones

    def _zone(self, raw: bytes) -> ZoneState:
        brightness, r, g, b = raw
        # device reports 0 for full brightness
        return ZoneState(brightness or 100, (r, g, b))


class GetZoneGroupV1(GetZoneGroup):
    """Legacy (pact V1) variant of `GetZoneGroup`. Has no brightness."""

    _command = PacketType.ZONE_COLORS_V1
    _stride = 3  # [r, g, b]

    def _zone(self, raw: bytes) -> ZoneState:
        r, g, b = raw
        return ZoneState(100, (r, g, b))


class SetZoneColorV1(Command):
    """
    Legacy (pact V1) variant of `SetZoneColor`, sub-mode 0x0B

    The kelvin field is looked up from the color table:
    a color that is not in it carries 2000 K (`07 D0`).
    """

    def __init__(self, rgb_color: RGBColor, zones: Iterable[int] | None = None):
        if not all(0 <= c <= 255 for c in rgb_color):
            raise ValueError("color components must be 0-255")

        self._color = rgb_color
        self._mask = zone_mask(zones)

    def payload(self):
        kelvin = kelvin_for_color(self._color) or MIN_KELVIN
        pkt = [ColorMode.STATIC_V1, *self._color, *kelvin.to_bytes(2, "big"), *self._mask]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetWhiteBalance(Command):
    """
    Set the video mode white balance (cmd 0xA9, type 0)

    Red and blue are only used when `auto` is off.
    """

    def __init__(self, white_balance: WhiteBalance):
        for name, value in (("red", white_balance.red), ("blue", white_balance.blue)):
            if not 1 <= value <= WHITE_BALANCE_MAX:
                raise ValueError(f"{name} must be 1-{WHITE_BALANCE_MAX}")

        self._wb = white_balance

    def payload(self):
        manual = int(not self._wb.auto)
        pkt = [VideoParam.WHITE_BALANCE, 3, manual, self._wb.red, self._wb.blue]

        return CommandPayload(PacketHeader.COMMAND, PacketType.VIDEO_PARAMS, pkt)


class GetWhiteBalance(CommandWithParser[WhiteBalanceState]):
    """Get the video mode white balance and the device default pair"""

    def payload(self):
        return CommandPayload(
            PacketHeader.STATUS, PacketType.VIDEO_PARAMS, [VideoParam.WHITE_BALANCE]
        )

    def parse_response(self, response: bytes):
        # [type, length, defAuto, defR, defB, manual, R, B]
        _, _, _, def_red, def_blue, manual, red, blue = response[:8]
        return WhiteBalanceState(WhiteBalance(not manual, red, blue), (def_red, def_blue))


class SetWholeScreenBrightness(Command):
    """
    Set the video mode brightness for the whole screen (cmd 0xA9, type 2)

    :param percent: 1-100
    """

    def __init__(self, percent: int):
        _check_percent("percent", percent)

        self._value = percent

    def payload(self):
        pkt = [VideoParam.WHOLE_SCREEN_BRIGHTNESS, 1, self._value]

        return CommandPayload(PacketHeader.COMMAND, PacketType.VIDEO_PARAMS, pkt)


class GetWholeScreenBrightness(CommandWithParser[int]):
    """Get the video mode brightness for the whole screen in percent"""

    def payload(self):
        return CommandPayload(
            PacketHeader.STATUS,
            PacketType.VIDEO_PARAMS,
            [VideoParam.WHOLE_SCREEN_BRIGHTNESS],
        )

    def parse_response(self, response: bytes):
        return response[2]


class SetGradient(Command):
    """Enable or disable smooth color gradient between zones"""

    def __init__(self, enabled: bool):
        self._enabled = enabled

    def payload(self):
        return CommandPayload(
            PacketHeader.COMMAND, PacketType.GRADIENT, [int(self._enabled)]
        )


class SetVideoEdgeBrightness(Command):
    """
    Set relative brightness of the screen edges in the video mode

    Only supported by firmware with segment brightness (hw 3.02.01 / 3.02.10,
    sw >= 1.10.02). All values 1-100 (range not verified on device).
    """

    def __init__(self, left: int, top: int, right: int, bottom: int):
        for name, value in (
            ("left", left),
            ("top", top),
            ("right", right),
            ("bottom", bottom),
        ):
            _check_percent(name, value)

        self._edges = [left, top, right, bottom]

    def payload(self):
        return CommandPayload(
            PacketHeader.COMMAND,
            PacketType.ZONE_RELATIVE_BRIGHTNESS,
            [0x01, 0x04, *self._edges],
        )


class GetVideoEdgeBrightness(CommandWithParser[EdgeBrightness]):
    """Get the relative brightness of the screen edges in video mode"""

    def payload(self):
        return CommandPayload(
            PacketHeader.STATUS, PacketType.ZONE_RELATIVE_BRIGHTNESS, [0x01]
        )

    def parse_response(self, response: bytes):
        # [1, N, left, top, right, bottom, ...]
        return EdgeBrightness(*response[2:6])


class GetGradient(CommandWithParser[bool]):
    """Get the state of the color gradient between zones"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.GRADIENT, [])

    def parse_response(self, response: bytes):
        return bool(response[0])


class SetBlackScreen(Command):
    """
    Set what the device does when the picture goes black (cmd 0xA9, type 0x0A)

    :raises ValueError: for a duration outside the range the protocol allows
        (see `BlackScreenSetting.normalized`).
    """

    def __init__(self, setting: BlackScreenSetting):
        for name, value, (low, high, _) in (
            ("low_brightness_seconds", setting.low_brightness_seconds, LOW_BRIGHTNESS_SECONDS),
            ("same_tone_seconds", setting.same_tone_seconds, SAME_TONE_SECONDS),
        ):
            if not low <= value <= high:
                raise ValueError(f"{name} must be {low}-{high}")

        self._setting = setting

    def payload(self):
        s = self._setting
        pkt = [
            VideoParam.BLACK_SCREEN,
            6,
            int(s.enabled),
            int(s.mode),
            *s.low_brightness_seconds.to_bytes(2, "little"),
            *s.same_tone_seconds.to_bytes(2, "little"),
        ]

        return CommandPayload(PacketHeader.COMMAND, PacketType.VIDEO_PARAMS, pkt)


class GetBlackScreen(CommandWithParser[BlackScreenSetting]):
    """Get what the device does when the picture goes black"""

    def payload(self):
        return CommandPayload(
            PacketHeader.STATUS, PacketType.VIDEO_PARAMS, [VideoParam.BLACK_SCREEN]
        )

    def parse_response(self, response: bytes):
        # [type, length, enabled, mode, d1Lo, d1Hi, d2Lo, d2Hi]
        enabled, mode = response[2], response[3]
        return BlackScreenSetting(
            bool(enabled),
            # anything but 1 is same tone
            BlackScreenMode.LOW_BRIGHTNESS if mode == 1 else BlackScreenMode.SAME_TONE,
            int.from_bytes(response[4:6], "little"),
            int.from_bytes(response[6:8], "little"),
        )
