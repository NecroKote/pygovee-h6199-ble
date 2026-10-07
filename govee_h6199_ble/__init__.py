from importlib.metadata import PackageNotFoundError, version

from .capabilities import Capabilities, ChipFamily, DeviceInfo, Version
from .colortemp import COLOR_TEMPERATURES, nearest_color_temperature
from .const import (
    ZONE_COUNT,
    ColorKind,
    ColorMode,
    MusicMode,
    PacketHeader,
    ProtocolGeneration,
)
from .device import GoveeH6199
from .errors import (
    CommandTimeout,
    GoveeError,
    InvalidResponse,
    NotStarted,
    TransportError,
    UnsupportedFeature,
)
from .events import (
    BrightnessChanged,
    DeviceEvent,
    Disconnected,
    MovieModeChanged,
    PowerChanged,
    SubDeviceStatus,
    UnknownNotification,
    WifiStateChanged,
    parse_notification,
)
from .model import (
    LOW_BRIGHTNESS_SECONDS,
    SAME_TONE_SECONDS,
    WHITE_BALANCE_MAX,
    WHITE_BALANCE_STEPS,
    BlackScreenMode,
    BlackScreenSetting,
    DeviceState,
    EdgeBrightness,
    Modes,
    MusicColorMode,
    Pact,
    RGBColor,
    StaticColorMode,
    UnknownColorMode,
    VideoColorMode,
    WhiteBalance,
    WhiteBalanceState,
    ZoneState,
)
from .transport import CommandTimeouts, Transport
from .util import connected

try:
    __version__ = version("govee-h6199-ble")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "COLOR_TEMPERATURES",
    "LOW_BRIGHTNESS_SECONDS",
    "SAME_TONE_SECONDS",
    "WHITE_BALANCE_MAX",
    "WHITE_BALANCE_STEPS",
    "ZONE_COUNT",
    "BlackScreenMode",
    "BlackScreenSetting",
    "BrightnessChanged",
    "Capabilities",
    "ChipFamily",
    "ColorKind",
    "ColorMode",
    "CommandTimeout",
    "CommandTimeouts",
    "DeviceEvent",
    "DeviceInfo",
    "DeviceState",
    "Disconnected",
    "EdgeBrightness",
    "GoveeError",
    "GoveeH6199",
    "InvalidResponse",
    "Modes",
    "MovieModeChanged",
    "MusicColorMode",
    "MusicMode",
    "NotStarted",
    "PacketHeader",
    "Pact",
    "PowerChanged",
    "ProtocolGeneration",
    "RGBColor",
    "StaticColorMode",
    "SubDeviceStatus",
    "Transport",
    "TransportError",
    "UnknownColorMode",
    "UnknownNotification",
    "UnsupportedFeature",
    "Version",
    "VideoColorMode",
    "WhiteBalance",
    "WhiteBalanceState",
    "WifiStateChanged",
    "ZoneState",
    "__version__",
    "connected",
    "nearest_color_temperature",
    "parse_notification",
]
