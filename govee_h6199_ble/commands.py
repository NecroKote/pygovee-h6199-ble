from .base import Command, CommandWithParser
from .const import ColorMode, MusicMode, PacketHeader, PacketType


class GetPowerState(CommandWithParser[bool]):
    def payload(self):
        return (PacketHeader.STATUS, PacketType.POWER, [])

    def parse_response(self, response: bytes):
        return bool(response[0])


class PowerOn(Command):
    def payload(self):
        return (PacketHeader.COMMAND, PacketType.POWER, [0x01])


class PowerOff(Command):
    def payload(self):
        return (PacketHeader.COMMAND, PacketType.POWER, [0x00])


class GetFirmwareVersion(CommandWithParser[str]):
    def payload(self):
        return (PacketHeader.STATUS, PacketType.FW, [])

    def parse_response(self, response: bytes):
        return str(response, encoding="ascii")


class GetHardwareVersion(CommandWithParser[str]):
    def payload(self):
        return (PacketHeader.STATUS, PacketType.HW, [0x03])

    def parse_response(self, response: bytes):
        return str(response, encoding="ascii")


class GetMacAddress(CommandWithParser[str]):
    def payload(self):
        return (PacketHeader.STATUS, PacketType.MAC, [])

    def parse_response(self, response: bytes):
        raw = response[:6]
        return ":".join((f"{x:02x}" for x in raw))


class SetBrightness(Command):
    def __init__(self, value: int):
        if not 0 <= value <= 100:
            raise ValueError("value must be 0-100")

        self._value = value

    def payload(self):
        return (PacketHeader.COMMAND, PacketType.BRIGHTNESS, [self._value])


class GetBrightness(CommandWithParser[int]):
    def payload(self):
        return (PacketHeader.STATUS, PacketType.BRIGHTNESS, [])

    def parse_response(self, response):
        return response[0]


class GetColorMode(CommandWithParser[ColorMode]):
    def payload(self):
        return (PacketHeader.STATUS, PacketType.COLOR, [])

    def parse_response(self, response):
        return ColorMode(response[0])


class SetStaticColor(Command):
    def __init__(
        self,
        color: tuple[int, int, int],
    ):
        self._color = color

    def payload(self):
        r, g, b = self._color
        pkt = [ColorMode.STATIC, 0x01, r, g, b] + ([0x00] * 5) + [0xFF, 0x7F]

        return (PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetMusicModeRythm(Command):
    def __init__(
        self,
        calm: bool = True,
        sensitivity: int = 100,
        color: tuple[int, int, int] | None = None,
    ):
        self._calm = calm
        self._color = color
        self._sensitivity = sensitivity

    def payload(self):
        pkt = [ColorMode.MUSIC, MusicMode.RYTHM, self._sensitivity, int(self._calm)]

        if self._color:
            r, g, b = self._color
            pkt += [0x01, r, g, b]

        return (PacketHeader.COMMAND, PacketType.COLOR, pkt)


class SetMusicModeEnergic(Command):
    def __init__(self, sensitivity: int = 100):
        self._sensitivity = sensitivity

    def payload(self):
        return (
            PacketHeader.COMMAND,
            PacketType.COLOR,
            [ColorMode.MUSIC, MusicMode.ENERGIC, self._sensitivity],
        )


class SetMusicModeSpectrum(Command):
    def __init__(
        self,
        sensitivity: int = 100,
        color: tuple[int, int, int] | None = None,
    ):
        self._color = color
        self._sensitivity = sensitivity

    def payload(self):
        pkt = [ColorMode.MUSIC, MusicMode.SPECTRUM, self._sensitivity, 0x00]

        if self._color:
            r, g, b = self._color
            pkt += [0x01, r, g, b]

        return (
            PacketHeader.COMMAND,
            PacketType.COLOR,
            pkt,
        )


class SetMusicModeRolling(Command):
    def __init__(
        self,
        sensitivity: int = 100,
        color: tuple[int, int, int] | None = None,
    ):
        self._color = color
        self._sensitivity = sensitivity

    def payload(self):
        pkt = [ColorMode.MUSIC, MusicMode.ROLLING, self._sensitivity, 0x00]

        if self._color:
            r, g, b = self._color
            pkt += [0x01, r, g, b]

        return (
            PacketHeader.COMMAND,
            PacketType.COLOR,
            pkt,
        )


class SetVideoMode(Command):
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

        return (PacketHeader.COMMAND, PacketType.COLOR, pkt)
