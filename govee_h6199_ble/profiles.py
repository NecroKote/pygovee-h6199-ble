"""
Per-generation command selection.

Each profile hides what differs between firmware generations behind one
interface, so the device facade never branches on versions.
"""

from abc import ABC, abstractmethod
from typing import Iterable, Sequence

from .capabilities import Capabilities
from .errors import UnsupportedFeature
from .model import RGBColor, ZoneState
from .protocol.base import Command, CommandWithParser
from .protocol.commands import (
    GetBrightness,
    GetZoneGroup,
    GetZoneGroupV1,
    SetBrightness,
    SetZoneBrightness,
    SetZoneBrightnessList,
    SetZoneColor,
    SetZoneColorTemperature,
    SetZoneColorTemperatureV1,
    SetZoneColorV1,
)


class ColorProfile(ABC):
    """Color, zone and brightness commands of one protocol generation"""

    @abstractmethod
    def set_brightness(self, percent: int) -> Command: ...

    @abstractmethod
    def get_brightness(self) -> CommandWithParser[int]: ...

    @abstractmethod
    def set_zone_color(
        self, color: RGBColor, zones: Iterable[int] | None
    ) -> Command: ...

    @abstractmethod
    def set_zone_color_temperature(
        self, kelvin: int, zones: Iterable[int] | None
    ) -> Command: ...

    @abstractmethod
    def set_zone_brightness(
        self, percent: int, zones: Iterable[int] | None
    ) -> Command: ...

    @abstractmethod
    def set_zone_brightness_list(self, percents: Sequence[int]) -> Command: ...

    @abstractmethod
    def get_zone_group(self, group: int) -> CommandWithParser[list[ZoneState]]: ...


class ColorProfileV2(ColorProfile):
    """Pact V2 and newer"""

    def set_brightness(self, percent):
        return SetBrightness(percent)

    def get_brightness(self):
        return GetBrightness()

    def set_zone_color(self, color, zones):
        return SetZoneColor(color, zones)

    def set_zone_color_temperature(self, kelvin, zones):
        return SetZoneColorTemperature(kelvin, zones)

    def set_zone_brightness(self, percent, zones):
        return SetZoneBrightness(percent, zones)

    def set_zone_brightness_list(self, percents):
        return SetZoneBrightnessList(percents)

    def get_zone_group(self, group):
        return GetZoneGroup(group)


class ColorProfileV1(ColorProfile):
    """Pact V1: sub-mode 0x0B, brightness 1-254, no zone brightness"""

    BRIGHTNESS_SCALE = 254

    def set_brightness(self, percent):
        return SetBrightness(percent, self.BRIGHTNESS_SCALE)

    def get_brightness(self):
        return GetBrightness(self.BRIGHTNESS_SCALE)

    def set_zone_color(self, color, zones):
        return SetZoneColorV1(color, zones)

    def set_zone_color_temperature(self, kelvin, zones):
        return SetZoneColorTemperatureV1(kelvin, zones)

    def set_zone_brightness(self, percent, zones):
        raise UnsupportedFeature("zone brightness", "not available on pact V1")

    def set_zone_brightness_list(self, percents):
        raise UnsupportedFeature("zone brightness", "not available on pact V1")

    def get_zone_group(self, group):
        return GetZoneGroupV1(group)


def color_profile(capabilities: Capabilities) -> ColorProfile:
    return ColorProfileV1() if capabilities.legacy_color else ColorProfileV2()
