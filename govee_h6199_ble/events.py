"""Events the device sends on its own (header 0xEE)"""

from dataclasses import dataclass
from typing import TypeAlias

from .protocol.const import NotificationType


@dataclass(frozen=True)
class BrightnessChanged:
    #: percent. Devices on pact V1 report 1-254, converted when that is known
    brightness: int


@dataclass(frozen=True)
class PowerChanged:
    on: bool


@dataclass(frozen=True)
class WifiStateChanged:
    connected: bool


@dataclass(frozen=True)
class MovieModeChanged:
    on: bool


@dataclass(frozen=True)
class SubDeviceStatus:
    """One byte per sub-device slot. Not meaningful for a single light."""

    slots: bytes


@dataclass(frozen=True)
class UnknownNotification:
    id: int
    payload: bytes


DeviceEvent: TypeAlias = (
    BrightnessChanged
    | PowerChanged
    | WifiStateChanged
    | MovieModeChanged
    | SubDeviceStatus
    | UnknownNotification
)


def parse_notification(notification_id: int, payload: bytes) -> DeviceEvent:
    """
    Decode a device-initiated frame.

    :param payload: frame bytes 2-18, so `payload[0]` is frame byte 2
    """

    try:
        kind = NotificationType(notification_id)
    except ValueError:
        return UnknownNotification(notification_id, payload)

    match kind:
        case NotificationType.WIFI_STATE:
            return WifiStateChanged(payload[0] == 0)

        case NotificationType.BRIGHTNESS:
            return BrightnessChanged(payload[0])

        case NotificationType.POWER:
            return PowerChanged(bool(payload[1] & 1))

        case NotificationType.SUB_DEVICES:
            return SubDeviceStatus(payload[:10])

        case NotificationType.MOVIE_MODE:
            # only meaningful when the first byte is 1
            if payload[0] == 1:
                return MovieModeChanged(payload[1] == 1)

    return UnknownNotification(notification_id, payload)
