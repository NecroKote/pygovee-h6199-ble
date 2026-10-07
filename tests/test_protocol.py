import pytest

from govee_h6199_ble import (
    BrightnessChanged,
    ColorKind,
    MovieModeChanged,
    MusicColorMode,
    MusicMode,
    PowerChanged,
    StaticColorMode,
    SubDeviceStatus,
    UnknownColorMode,
    UnknownNotification,
    VideoColorMode,
    WifiStateChanged,
    parse_notification,
)
from govee_h6199_ble.protocol import commands as c
from govee_h6199_ble.protocol.colortemp import (
    COLOR_TEMPERATURES,
    kelvin_for_color,
    nearest_color_temperature,
    tint_for_kelvin,
)
from govee_h6199_ble.protocol.const import PacketHeader, ProtocolGeneration
from govee_h6199_ble.protocol.packet import (
    checksum,
    make_frame,
    unpack_frame,
    zone_mask,
)


@pytest.mark.parametrize(
    "note,payload,event",
    [
        (0x11, b"\0", WifiStateChanged(True)),
        (0x11, b"\1", WifiStateChanged(False)),
        (0x20, b"\x37", BrightnessChanged(55)),
        (0x30, b"\0\3", PowerChanged(True)),
        (0x30, b"\0\2", PowerChanged(False)),
        (0x40, bytes(range(12)), SubDeviceStatus(bytes(range(10)))),
        (0x60, b"\1\1", MovieModeChanged(True)),
        (0x60, b"\1\0", MovieModeChanged(False)),
        (0x60, b"\0\1", UnknownNotification(0x60, b"\0\1")),
        (0x99, b"abc", UnknownNotification(0x99, b"abc")),
    ],
)
def test_notifications(note, payload, event):
    assert parse_notification(note, payload) == event


@pytest.mark.parametrize(
    "note,minimum", [(0x11, 1), (0x20, 1), (0x30, 2), (0x40, 10), (0x60, 2)]
)
def test_short_notifications(note, minimum):
    for length in range(minimum):
        payload = bytes(length)
        assert parse_notification(note, payload) == UnknownNotification(note, payload)


def test_frame_round_trip_and_checksum():
    frame = make_frame(PacketHeader.COMMAND, 5, [1, 2, 255])
    assert len(frame) == 20
    assert checksum(frame) == 0
    assert unpack_frame(frame) == (0x33, 5, bytes([1, 2, 255]) + bytes(14))
    assert checksum(b"\x33\x05\x01") == 0x37


@pytest.mark.parametrize("frame", [b"", bytes(19), bytes(21), b"\x33" + bytes(19)])
def test_bad_frames(frame):
    with pytest.raises(ValueError):
        unpack_frame(frame)


def test_frame_payload_limits():
    assert len(make_frame(0x33, 5, list(range(17)))) == 20
    for payload in [list(range(18)), [-1], [256]]:
        with pytest.raises(ValueError):
            make_frame(0x33, 5, payload)


def test_zone_masks():
    assert zone_mask() == (255, 127)
    assert zone_mask([0, 8, 14, 8]) == (1, 65)
    for zones in [[], [-1], [15]]:
        with pytest.raises(ValueError):
            zone_mask(zones)


def test_color_temperature_table_round_trips():
    for kelvin in COLOR_TEMPERATURES:
        assert nearest_color_temperature(kelvin) == kelvin
        assert kelvin_for_color(tint_for_kelvin(kelvin)) == kelvin
    assert kelvin_for_color((255, 209, 163)) == 4000  # second column
    assert kelvin_for_color((1, 2, 3)) is None
    assert nearest_color_temperature(4550) == 4500
    assert nearest_color_temperature(6750) == 6500
    for invalid in [1999, 9001]:
        with pytest.raises(ValueError):
            nearest_color_temperature(invalid)
    with pytest.raises(ValueError):
        tint_for_kelvin(4550)


@pytest.mark.parametrize(
    "payload,mode",
    [
        ([0, 1, 0, 70, 1, 30, 60], VideoColorMode(True, False, 70, True, 30, 60)),
        ([0, 1, 0, 0, 0, 0, 0], VideoColorMode(True, False, None, False, None, None)),
        ([0x13, 3], MusicColorMode(MusicMode.RHYTHM)),
        ([0x13, 99], UnknownColorMode(0x13)),
        ([0x15, 1], StaticColorMode(ColorKind.COLOR)),
        ([0x15, 0], StaticColorMode()),
        ([0x0B], StaticColorMode()),
        ([0xFF], UnknownColorMode(0xFF)),
        ([4], UnknownColorMode(4)),
    ],
)
def test_mode_parser(payload, mode):
    assert c.GetColorMode().parse_response(bytes(payload)) == mode


@pytest.mark.parametrize(
    "command,domain,payload",
    [
        (c.PowerOn(), 1, [1]),
        (c.PowerOff(), 1, [0]),
        (c.SetBrightness(50), 4, [50]),
        (c.SetBrightness(100, 254), 4, [254]),
        (c.SetMusicModeRhythm(False, 50, (1, 2, 3)), 5, [0x13, 3, 50, 0, 1, 1, 2, 3]),
        (c.SetMusicModeEnergic(20), 5, [0x13, 5, 20]),
        (c.SetMusicModeSpectrum(30), 5, [0x13, 4, 30, 0]),
        (c.SetMusicModeRolling(40, (1, 2, 3)), 5, [0x13, 6, 40, 0, 1, 1, 2, 3]),
        (c.SetVideoMode(), 5, [0, 1, 0, 50, 0, 50]),
        (c.SetZoneBrightness(30, [14]), 5, [0x15, 2, 30, 0, 64]),
        (c.SetZoneBrightnessList([50] * 15), 5, [0x15, 3] + [50] * 15),
        (c.SetWholeScreenBrightness(40), 0xA9, [2, 1, 40]),
        (c.SetVideoEdgeBrightness(10, 20, 30, 40), 0xAE, [1, 4, 10, 20, 30, 40]),
        (c.SetGradient(True), 0xA3, [1]),
    ],
)
def test_command_payloads(command, domain, payload):
    actual = command.payload()
    assert actual == (PacketHeader.COMMAND, domain, payload)
    assert len(make_frame(*actual)) == 20


@pytest.mark.parametrize(
    "factory",
    [
        lambda: c.SetBrightness(0),
        lambda: c.SetBrightness(101),
        lambda: c.SetVideoMode(saturation=0),
        lambda: c.SetVideoMode(sound_effects_softness=101),
        lambda: c.SetVideoMode(brightness=0),
        lambda: c.SetMusicModeRhythm(sensitivity=100),
        lambda: c.SetMusicModeEnergic(-1),
        lambda: c.SetMusicModeSpectrum(100),
        lambda: c.SetMusicModeRolling(100),
        lambda: c.SetMusicModeSpectrum(rgb_color=(1, 2)),
        lambda: c.SetZoneColor((256, 0, 0)),
        lambda: c.SetZoneColor((0, 0)),
        lambda: c.SetZoneColorV1((-1, 0, 0)),
        lambda: c.SetZoneColorTemperature(4550),
        lambda: c.SetZoneColorTemperatureV1(1999),
        lambda: c.SetZoneBrightness(0),
        lambda: c.SetZoneBrightnessList([1] * 14),
        lambda: c.SetZoneBrightnessList([0] * 15),
        lambda: c.GetZoneGroup(5),
        lambda: c.SetWholeScreenBrightness(101),
        lambda: c.SetVideoEdgeBrightness(1, 2, 3, 0),
    ],
)
def test_command_validation_is_early(factory):
    with pytest.raises(ValueError):
        factory()


def test_static_command_supports_legacy_generation():
    assert (
        c.SetStaticColor((1, 2, 3), ProtocolGeneration.V1).payload()
        == c.SetZoneColorV1((1, 2, 3)).payload()
    )
    assert c.SetStaticColor((1, 2, 3)).payload() == c.SetZoneColor((1, 2, 3)).payload()
    assert c.SetMusicModeRythm is c.SetMusicModeRhythm


@pytest.mark.parametrize(
    "command,response,result",
    [
        (c.GetPowerState(), b"\1", True),
        (c.GetBrightness(254), b"\x7f", 50),
        (c.GetFirmwareVersion(), b"1.10.04", "1.10.04"),
        (c.GetHardwareVersion(), b"\x033.02.01", "3.02.01"),
        (c.GetWifiFirmwareVersion(), b"v1.00.30\0", "1.00.30"),
        (c.GetWifiHardwareVersion(), b"1.03.00\0", "1.03.00"),
        (c.GetMacAddress(), bytes(range(6)), "00:01:02:03:04:05"),
        (c.GetPact(), bytes([0, 2, 1]), (2, 1)),
        (c.GetWholeScreenBrightness(), bytes([2, 1, 70]), 70),
        (c.GetVideoEdgeBrightness(), bytes([1, 4, 10, 20, 30, 40]), (10, 20, 30, 40)),
        (c.GetGradient(), b"\1", True),
    ],
)
def test_command_parsers(command, response, result):
    assert command.payload().header == PacketHeader.STATUS
    assert command.parse_response(response) == result


def test_zone_group_parser_ignores_padding():
    states = c.GetZoneGroup(4).parse_response(bytes([4] + [0, 1, 2, 3] * 4))
    assert states == [(100, (1, 2, 3))] * 3
    assert c.GetZoneGroupV1(4).parse_response(bytes([4] + [1, 2, 3] * 4)) == states
