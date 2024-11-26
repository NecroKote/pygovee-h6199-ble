from enum import IntEnum

UUID_NOTIFY_CHARACTERISTIC = "00010203-0405-0607-0809-0a0b0c0d2b10"
UUID_CONTROL_CHARACTERISTIC = "00010203-0405-0607-0809-0a0b0c0d2b11"


class PacketHeader(IntEnum):
    STATUS = 0xAA
    COMMAND = 0x33


class PacketType(IntEnum):
    POWER = 0x01
    BRIGHTNESS = 0x04
    COLOR = 0x05
    FW = 0x06
    HW = 0x07
    MAC = 0x014
    HW_LOW = 0x20
    HW_HI = 0x21


class ColorMode(IntEnum):
    VIDEO = 0x00
    MUSIC = 0x13
    STATIC = 0x15


class MusicMode(IntEnum):
    RYTHM = 0x03
    SPECTRUM = 0x04
    ENERGIC = 0x05
    ROLLING = 0x06
