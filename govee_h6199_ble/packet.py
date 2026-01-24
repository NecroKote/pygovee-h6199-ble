def checksum(data: bytes):
    """Calculate checksum by XORing all bytes in data."""

    checksum = 0
    for b in data:
        checksum ^= b
    return checksum & 0xFF


def make_frame(cmd: int, group: int, payload: list[int]) -> bytes:
    """Construct a 20-byte frame with given command, group, and payload."""

    if len(payload) > 17:
        raise ValueError("Payload too long")

    frame = bytearray(20)
    frame[0] = cmd
    frame[1] = group & 0xFF

    for idx, byte in enumerate(payload):
        frame[idx + 2] = byte

    frame[19] = checksum(frame[:-1])

    return bytes(frame)


def unpack_frame(frame: bytes) -> tuple[int, int, bytes]:
    """Unpack a response frame into command, group, and payload."""

    cmd, group, *payload, _ = frame
    return cmd, group, bytes(payload)
