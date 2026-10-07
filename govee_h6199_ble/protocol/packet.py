from collections.abc import Iterable

from .const import ZONE_COUNT


def checksum(data: bytes):
    """Calculate checksum by XORing all bytes in data."""

    checksum = 0
    for b in data:
        checksum ^= b
    return checksum & 0xFF


def make_frame(header: int, command: int, payload: list[int]) -> bytes:
    """Construct a 20-byte frame with given header, command id, and payload."""

    if len(payload) > 17:
        raise ValueError("Payload too long")

    frame = bytearray(20)
    frame[0] = header & 0xFF
    frame[1] = command & 0xFF

    for idx, byte in enumerate(payload):
        frame[idx + 2] = byte

    frame[19] = checksum(frame[:-1])

    return bytes(frame)


def unpack_frame(frame: bytes) -> tuple[int, int, bytes]:
    """Unpack a response frame into header, command id, and payload."""

    if len(frame) != 20:
        raise ValueError("frame must be exactly 20 bytes")
    if checksum(frame[:-1]) != frame[-1]:
        raise ValueError("invalid frame checksum")

    header, command, *payload, _ = frame
    return header, command, bytes(payload)


def zone_mask(zones: Iterable[int] | None = None) -> tuple[int, int]:
    """
    Build the two zone mask bytes (zones 0-7, zones 8-14).

    `None` selects all zones.
    """

    if zones is None:
        zones = range(ZONE_COUNT)

    mask = 0
    for zone in zones:
        if not 0 <= zone < ZONE_COUNT:
            raise ValueError(f"zone must be 0-{ZONE_COUNT - 1}, got {zone}")
        mask |= 1 << zone

    if not mask:
        raise ValueError("no zones selected")

    return mask & 0xFF, (mask >> 8) & 0xFF
