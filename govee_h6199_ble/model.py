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


@dataclass
class MusicColorMode:
    mode = ColorMode.MUSIC

    music_mode: MusicMode


@dataclass
class StaticColorMode:
    mode = ColorMode.STATIC


@dataclass
class UnknownColorMode:
    mode: int


Modes: TypeAlias = VideoColorMode | MusicColorMode | StaticColorMode | UnknownColorMode
