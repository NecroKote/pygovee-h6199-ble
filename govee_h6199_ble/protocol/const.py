from enum import IntEnum

UUID_SERVICE = "00010203-0405-0607-0809-0a0b0c0d1910"
UUID_NOTIFY_CHARACTERISTIC = "00010203-0405-0607-0809-0a0b0c0d2b10"
UUID_CONTROL_CHARACTERISTIC = "00010203-0405-0607-0809-0a0b0c0d2b11"

ZONE_COUNT = 15
ZONE_GROUP_SIZE = 4


class PacketHeader(IntEnum):
    STATUS = 0xAA
    COMMAND = 0x33
    #: sent by the device on its own, not as a reply
    NOTIFICATION = 0xEE


class NotificationType(IntEnum):
    """Id byte of a device-initiated (0xEE) frame"""

    WIFI_STATE = 0x11
    BRIGHTNESS = 0x20
    POWER = 0x30
    SUB_DEVICES = 0x40
    MOVIE_MODE = 0x60


class PacketType(IntEnum):
    POWER = 0x01
    BRIGHTNESS = 0x04
    COLOR = 0x05
    FW = 0x06
    HW = 0x07
    MAC = 0x14  # Wi-Fi module
    WIFI_HW = 0x20
    WIFI_SW = 0x21
    PACT = 0xEF
    GRADIENT = 0xA3
    ZONE_COLORS = 0xA5
    ZONE_COLORS_V1 = 0xA2
    VIDEO_PARAMS = 0xA9
    ZONE_RELATIVE_BRIGHTNESS = 0xAE


class ColorMode(IntEnum):
    VIDEO = 0x00
    SCENE = 0x04
    DIY = 0x0A
    STATIC_V1 = 0x0B
    MUSIC_LEGACY = 0x0C
    MUSIC = 0x13
    STATIC = 0x15

    UNKNOWN = 0xFF


class VideoParam(IntEnum):
    """Type byte of the 0xA9 video parameters command"""

    WHITE_BALANCE = 0x00
    GAME_SENSITIVITY = 0x01
    WHOLE_SCREEN_BRIGHTNESS = 0x02
    BLACK_SCREEN = 0x0A


class ProtocolGeneration(IntEnum):
    """Protocol generation (pact), V1-V4. Value is the pact type"""

    V1 = 1
    V2 = 2
    V3 = 3
    V4 = 4


class ColorKind(IntEnum):
    """Second byte of a STATIC (0x15) mode frame"""

    COLOR = 0x01
    ZONE_BRIGHTNESS = 0x02
    ZONE_BRIGHTNESS_LIST = 0x03


class MusicMode(IntEnum):
    RYTHM = 0x03
    SPECTRUM = 0x04
    ENERGIC = 0x05
    ROLLING = 0x06
