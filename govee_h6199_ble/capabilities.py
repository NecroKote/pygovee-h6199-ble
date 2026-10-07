"""
Feature gating by firmware / hardware / protocol generation.

Implements section 5 of the H6199 protocol notes. The function is pure so it
can be used on cached versions; `GoveeH6199.get_capabilities` reads the inputs
from a live device.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from .const import ProtocolGeneration
from .model import Pact


class Version(NamedTuple):
    """Dotted version, e.g. `1.10.04`. Compares numerically."""

    major: int
    minor: int = 0
    patch: int = 0

    @classmethod
    def parse(cls, text: str) -> "Version":
        parts = re.findall(r"\d+", text)[:3]
        if not parts:
            raise ValueError(f"not a version: {text!r}")

        return cls(*(int(p) for p in parts))

    def __str__(self):
        return f"{self.major}.{self.minor:02d}.{self.patch:02d}"


class ChipFamily(Enum):
    TELINK = "telink"  # hard 1.x
    BK = "bk"  # hard 2.01
    FRK = "frk"  # hard 3.x
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DeviceInfo:
    """Version inputs of the capability check"""

    soft: Version
    hard: Version
    wifi_soft: Version | None = None
    wifi_hard: Version | None = None
    pact: Pact | None = None


@dataclass(frozen=True)
class Capabilities:
    chip: ChipFamily

    #: pact V1: color sub-mode 0x0B, brightness 1-254, no zone brightness
    legacy_color: bool
    #: color sub-mode 0x15 brightness frames (pact V2+)
    zone_brightness: bool
    service_scenes: bool
    ai_effects: bool
    phone_mic_music: bool
    #: cmd 0xA9 type 0
    white_balance: bool
    #: cmd 0xA9 type 2 (or byte 6 of the video frame on Telink)
    video_brightness: bool
    #: cmd 0xAE; replaces `video_brightness` when available
    video_segment_brightness: bool
    #: cmd 0xA9 type 0x0A, same gate as segment brightness
    black_screen: bool

    @classmethod
    def from_info(cls, info: DeviceInfo) -> "Capabilities":
        return from_info(info)


_FIRST_NEWER_FRK = Version(3, 2, 1)
_REFERENCE_REVISIONS = (Version(3, 2, 1), Version(3, 2, 10))


def _chip(hard: Version) -> ChipFamily:
    if hard.major == 1:
        return ChipFamily.TELINK
    if (hard.major, hard.minor) == (2, 1):
        return ChipFamily.BK
    if hard.major == 3:
        return ChipFamily.FRK
    return ChipFamily.UNKNOWN


def _at_least(value: Version | None, minimum: Version) -> bool:
    return value is not None and value >= minimum


def _wifi_ok(info: DeviceInfo, soft: Version, hard: Version | None = None) -> bool:
    return _at_least(info.wifi_soft, soft) and (
        hard is None or _at_least(info.wifi_hard, hard)
    )


def _generation(info: DeviceInfo) -> ProtocolGeneration | None:
    return info.pact.generation if info.pact else None


def from_info(info: DeviceInfo) -> Capabilities:
    """
    Work out what a device supports.

    Unknown hardware families get nothing except the pact based features.
    A missing or unknown pact does not enable generation-specific features.
    """

    chip = _chip(info.hard)
    gen = _generation(info)
    soft, hard = info.soft, info.hard

    service_scenes = gen in (ProtocolGeneration.V3, ProtocolGeneration.V4)
    ai_effects = gen == ProtocolGeneration.V4
    phone_mic = False
    white_balance = False
    video_brightness = False
    segment_brightness = False

    if chip == ChipFamily.TELINK:
        service_scenes |= soft >= Version(1, 6, 1)
        ai_effects |= soft >= Version(1, 6, 1)
        phone_mic = soft >= Version(1, 1, 0)
        video_brightness = (
            gen == ProtocolGeneration.V1
            and soft >= Version(1, 7, 1)
            and _wifi_ok(info, Version(1, 0, 28), Version(1, 0, 1))
        )

    elif chip == ChipFamily.FRK:
        # hard 3.04 is the "AI" variant: scenes only from the pact
        if (hard.major, hard.minor) != (3, 4):
            service_scenes |= soft >= Version(1, 7, 2)
        ai_effects |= soft >= Version(1, 7, 2)
        phone_mic = soft >= Version(1, 1, 0)

        if hard >= _FIRST_NEWER_FRK:  # tables C and D
            white_balance = soft >= Version(1, 8, 11) and _wifi_ok(
                info, Version(1, 0, 23), Version(1, 3, 0)
            )

            option1 = (
                soft >= Version(1, 9, 11)
                and _wifi_ok(info, Version(1, 0, 28))
                and info.wifi_hard is not None
                and info.wifi_hard[:2] == (1, 0)
            )
            option2 = soft >= Version(1, 9, 11) and _wifi_ok(
                info, Version(1, 0, 29), Version(1, 3, 0)
            )

            if hard in _REFERENCE_REVISIONS:
                segment_brightness = (
                    soft >= Version(1, 10, 2)
                    and _wifi_ok(info, Version(1, 0, 30))
                    and info.wifi_hard == Version(1, 3, 0)
                )

            video_brightness = (option1 or option2) and not segment_brightness

    return Capabilities(
        chip=chip,
        legacy_color=gen == ProtocolGeneration.V1,
        zone_brightness=gen
        in (ProtocolGeneration.V2, ProtocolGeneration.V3, ProtocolGeneration.V4),
        service_scenes=service_scenes,
        ai_effects=ai_effects,
        phone_mic_music=phone_mic,
        white_balance=white_balance,
        video_brightness=video_brightness,
        video_segment_brightness=segment_brightness,
        black_screen=segment_brightness,
    )
