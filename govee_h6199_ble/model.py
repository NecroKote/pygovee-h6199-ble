from dataclasses import dataclass
from enum import IntEnum
from typing import NamedTuple
from typing import TypeAlias

from .protocol.colortemp import kelvin_for_color
from .protocol.const import ColorKind, ColorMode, MusicMode, ProtocolGeneration

RGBColor: TypeAlias = tuple[int, int, int]


class ZoneState(NamedTuple):
    """State of a single zone as reported by the device"""

    brightness: int  # 1-100
    color: RGBColor

    @property
    def kelvin(self) -> int | None:
        """Color temperature, if the color is one of the color table's colors"""

        return kelvin_for_color(self.color)


class Pact(NamedTuple):
    """Protocol id of the device, as in the advertisement"""

    type: int
    code: int

    @property
    def generation(self) -> ProtocolGeneration | None:
        """Known protocol generation, `None` if the pair is not registered"""

        if self.code != 1:
            return None

        try:
            return ProtocolGeneration(self.type)
        except ValueError:
            return None


#: (red, blue) pairs of the 20 defined white balance steps
WHITE_BALANCE_STEPS: tuple[tuple[int, int], ...] = (
    (7, 10),
    (8, 8),
    (9, 5),
    (10, 8),
    (10, 6),
    (11, 6),
    (12, 7),
    (12, 6),
    (13, 5),
    (13, 3),
    (14, 5),
    (14, 3),
    (15, 4),
    (15, 3),
    (16, 5),
    (16, 4),
    (16, 3),
    (18, 6),
    (18, 4),
    (21, 5),
)

#: the device ignores a white balance write with red or blue outside 1-31
WHITE_BALANCE_MAX = 31


class WhiteBalance(NamedTuple):
    """
    Video mode white balance. `red` / `blue` are used when `auto` is off.

    The protocol defines the pairs of `WHITE_BALANCE_STEPS`; `from_step` builds
    one. Any red / blue in 1-31 is accepted by the device, anything else makes
    it ignore the whole write.
    """

    auto: bool
    red: int = 16
    blue: int = 3

    @classmethod
    def from_step(cls, step: int) -> "WhiteBalance":
        """Manual white balance of a defined step, 1-20"""

        if not 1 <= step <= len(WHITE_BALANCE_STEPS):
            raise ValueError(f"step must be 1-{len(WHITE_BALANCE_STEPS)}")

        return cls(False, *WHITE_BALANCE_STEPS[step - 1])

    @property
    def step(self) -> int | None:
        """Slider step (1-20) of the red / blue pair, `None` if it is not one"""

        try:
            return WHITE_BALANCE_STEPS.index((self.red, self.blue)) + 1
        except ValueError:
            return None


class WhiteBalanceState(NamedTuple):
    """White balance as reported by the device"""

    current: WhiteBalance
    #: (red, blue) the device reports as its own default
    default: tuple[int, int]


class BlackScreenMode(IntEnum):
    LOW_BRIGHTNESS = 1
    SAME_TONE = 2


#: what the protocol allows, in seconds: (minimum, maximum, default)
LOW_BRIGHTNESS_SECONDS = (5, 300, 10)
SAME_TONE_SECONDS = (120, 1800, 300)


class BlackScreenSetting(NamedTuple):
    """
    What the device does when the picture goes black in video mode: keep the
    lights at the same tone, or switch to low brightness.

    Both durations are always sent. A value outside its range is not valid,
    `normalized()` replaces it with the default.
    """

    enabled: bool
    mode: BlackScreenMode = BlackScreenMode.LOW_BRIGHTNESS
    #: seconds before the low brightness applies, 5-300
    low_brightness_seconds: int = LOW_BRIGHTNESS_SECONDS[2]
    #: seconds the same tone is kept, 120-1800
    same_tone_seconds: int = SAME_TONE_SECONDS[2]

    def normalized(self) -> "BlackScreenSetting":
        low, same = self.low_brightness_seconds, self.same_tone_seconds
        if not LOW_BRIGHTNESS_SECONDS[0] <= low <= LOW_BRIGHTNESS_SECONDS[1]:
            low = LOW_BRIGHTNESS_SECONDS[2]
        if not SAME_TONE_SECONDS[0] <= same <= SAME_TONE_SECONDS[1]:
            same = SAME_TONE_SECONDS[2]

        return self._replace(low_brightness_seconds=low, same_tone_seconds=same)


class EdgeBrightness(NamedTuple):
    """Relative brightness of the screen edges in video mode, 1-100"""

    left: int
    top: int
    right: int
    bottom: int


@dataclass
class VideoColorMode:
    mode = ColorMode.VIDEO

    full_screen: bool
    game_mode: bool
    saturation: int
    sound_effects: bool = False
    sound_effects_softness: int = 0
    brightness: int = 0


@dataclass
class MusicColorMode:
    mode = ColorMode.MUSIC

    music_mode: MusicMode


@dataclass
class StaticColorMode:
    mode = ColorMode.STATIC

    #: kind of the last static frame, `None` if the device didn't say
    kind: ColorKind | None = None
    #: colors and brightness per zone, filled by `GoveeH6199.get_mode`
    zones: list[ZoneState] | None = None


@dataclass
class UnknownColorMode:
    mode: int  # raw sub-mode byte


Modes: TypeAlias = VideoColorMode | MusicColorMode | StaticColorMode | UnknownColorMode


@dataclass
class DeviceState:
    """Snapshot returned by `GoveeH6199.read_state`"""

    power: bool
    brightness: int
    mode: Modes
    zones: list[ZoneState]
