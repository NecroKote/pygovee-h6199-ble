from dataclasses import dataclass
from typing import TypeAlias

from .const import ColorMode, MusicMode

RGBColor: TypeAlias = tuple[int, int, int]


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


@dataclass
class UnknownColorMode:
    mode: int  # raw sub-mode byte


Modes: TypeAlias = VideoColorMode | MusicColorMode | StaticColorMode | UnknownColorMode
