from .base import Command, CommandPayload, CommandWithParser
from .const import ColorMode, MusicMode, PacketHeader, PacketType
from .model import (
    Modes,
    MusicColorMode,
    RGBColor,
    StaticColorMode,
    UnknownColorMode,
    VideoColorMode,
)


class GetStatus(CommandWithParser[bytes]):
    """
    Get the status of the specific domain

    Equivalent to: calling `command_with_reply` with `PacketHeader.STATUS`
    and `domain` as the first byte
    """

    def __init__(self, domain: int, payload: list[int] = []):
        self._domain = domain
        self._payload = payload

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
        return str(response[0:8], encoding="ascii")


class GetHardwareVersion(CommandWithParser[str]):
    """Get the hardware version of the device"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.HW, [0x03])

    def parse_response(self, response: bytes):
        return str(response[1:8], encoding="ascii")


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
    """

    def __init__(self, percent: int):
        if not 1 <= percent <= 100:
            raise ValueError("value must be 1-100")

        self._value = percent

    def payload(self):
        return CommandPayload(
            PacketHeader.COMMAND, PacketType.BRIGHTNESS, [self._value]
        )


class GetBrightness(CommandWithParser[int]):
    """Get the brightness of the device in percent"""

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.BRIGHTNESS, [])

    def parse_response(self, response):
        return response[0]


class GetColorMode(CommandWithParser[Modes]):
    """
    Get the current mode the device is in
    """

    def payload(self):
        return CommandPayload(PacketHeader.STATUS, PacketType.COLOR, [])

    def parse_response(self, response):
        mode = ColorMode(response[0])
        match mode:
            case ColorMode.VIDEO:
                full_screen = bool(response[1])
                game_mode = bool(response[2])
                saturation = response[3]
                return VideoColorMode(full_screen, game_mode, saturation)

            case ColorMode.MUSIC:
                music_mode = MusicMode(response[1])
                return MusicColorMode(music_mode)

            case ColorMode.STATIC:
                # HINT: the current fw version (1.10.04) doesn't seem to return the static color
                return StaticColorMode()

        return UnknownColorMode(mode)


class SetStaticColor(Command):
    """Switch the device in the Static Color mode"""

    def __init__(
        self,
        rgb_color: RGBColor,
    ):
        self._color = rgb_color

    def payload(self):
        r, g, b = self._color
        pkt = [ColorMode.STATIC, 0x01, r, g, b] + ([0x00] * 5) + [0xFF, 0x7F]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetMusicModeRythm(Command):
    """Switch the device in the Music mode with Rythm effect"""

    def __init__(
        self,
        calm: bool = True,
        sensitivity: int = 100,
        rgb_color: RGBColor | None = None,
    ):
        if not 0 <= sensitivity <= 100:
            raise ValueError("sensitivity must be 0-100")

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

    def __init__(self, sensitivity: int = 100):
        if not 0 <= sensitivity <= 100:
            raise ValueError("sensitivity must be 0-100")

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
        sensitivity: int = 100,
        rgb_color: RGBColor | None = None,
    ):
        if not 0 <= sensitivity <= 100:
            raise ValueError("sensitivity must be 0-100")

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
        sensitivity: int = 100,
        rgb_color: RGBColor | None = None,
    ):
        if not 0 <= sensitivity <= 100:
            raise ValueError("sensitivity must be 0-100")

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
    """Switch the device in the Video mode a.k.a Camera mode"""

    def __init__(
        self,
        full_screen: bool = True,
        game_mode: bool = False,
        saturation: int = 100,
        sound_effects: bool = False,
        sound_effects_softness: int = 0,
    ):
        if not 0 <= saturation <= 100:
            raise ValueError("saturation must be 0-100")

        if not 0 <= sound_effects_softness <= 100:
            raise ValueError("sound_effects_softness must be 0-100")

        self._full_screen = full_screen
        self._saturation = saturation
        self._game_mode = game_mode
        self._sound_effects = sound_effects
        self._sound_effects_softness = sound_effects_softness

    def payload(self):
        pkt = [
            ColorMode.VIDEO,
            int(self._full_screen),
            int(self._game_mode),
            self._saturation,
        ]

        if self._sound_effects:
            pkt += [0x01, self._sound_effects_softness]

        return CommandPayload(PacketHeader.COMMAND, PacketType.COLOR, pkt)
