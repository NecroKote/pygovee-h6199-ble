import asyncio
from collections.abc import Callable

import pytest

from govee_h6199_ble import (
    WHITE_BALANCE_STEPS,
    BlackScreenMode,
    BlackScreenSetting,
    BrightnessChanged,
    ColorKind,
    DeviceInfo,
    GoveeH6199,
    MovieModeChanged,
    PowerChanged,
    StaticColorMode,
    UnknownNotification,
    UnsupportedFeature,
    Version,
    WhiteBalance,
    WifiStateChanged,
)
from govee_h6199_ble.model import Pact
from govee_h6199_ble.protocol.commands import GetWifiHardwareVersion
from govee_h6199_ble.protocol.packet import make_frame


class FakeClient:
    """Stands in for BleakClient: records frames and acks each of them."""

    def __init__(
        self,
        replies: dict[int, list[int] | Callable] | None = None,
        unsolicited: list[bytes] | None = None,
    ):
        self.frames: list[bytes] = []
        self._unsolicited = unsolicited or []
        self._replies = replies or {}
        self._callback = None
        self.is_connected = True

    async def start_notify(self, _, callback):
        self._callback = callback

    async def stop_notify(self, _):
        pass

    async def write_gatt_char(self, _, frame, response=False):
        self.frames.append(frame)
        cmd = frame[1]
        payload = self._replies.get(cmd, [])
        if callable(payload):
            payload = payload(frame)
        reply = make_frame(frame[0], cmd, payload)
        for pushed in self._unsolicited:
            asyncio.get_running_loop().call_soon(
                self._callback, None, bytearray(pushed)
            )
        asyncio.get_running_loop().call_soon(self._callback, None, bytearray(reply))


def v(s):
    return Version.parse(s) if s else None


def device_info(soft, hard, wifi_soft=None, wifi_hard=None, pact=(4, 1)):
    return DeviceInfo(v(soft), v(hard), v(wifi_soft), v(wifi_hard), Pact(*pact))


REFERENCE = device_info("1.10.04", "3.02.01", "1.00.30", "1.03.00")
V1_DEVICE = device_info("1.07.01", "1.02.00", "1.00.28", "1.00.01", pact=(1, 1))
OLD_FRK = device_info("1.10.04", "3.02.00", pact=(2, 1))


def run(info, action, replies=None, unsolicited=None, **kwargs):
    client = FakeClient(replies, unsolicited)

    async def go():
        async with GoveeH6199(client, device_info=info, **kwargs) as device:
            return await action(device)

    result = asyncio.run(go())
    return result, [f.hex() for f in client.frames]


def test_zone_colors_share_frames_by_color():
    red, blue = (255, 0, 0), (0, 0, 255)
    _, frames = run(REFERENCE, lambda d: d.set_zone_colors({0: red, 1: blue, 8: red}))
    assert len(frames) == 2
    assert frames[0].startswith("33051501ff000000000000000101")  # zones 0 and 8
    assert frames[1].startswith("33051501" + "0000ff" + "0000000000" + "0200")


def test_zone_colors_sequence_needs_15():
    with pytest.raises(ValueError):
        run(REFERENCE, lambda d: d.set_zone_colors([(0, 0, 0)] * 3))


def test_v1_uses_legacy_color_frame():
    _, frames = run(V1_DEVICE, lambda d: d.set_static_color((1, 2, 3)))
    assert frames[0].startswith("33050b01020307d0ff7f")


def test_v1_brightness_scaled_to_254():
    _, frames = run(V1_DEVICE, lambda d: d.set_brightness(100))
    assert frames[0].startswith("3304fe")
    _, frames = run(V1_DEVICE, lambda d: d.set_brightness(1))
    assert frames[0].startswith("330403")


def test_v1_has_no_zone_brightness():
    with pytest.raises(UnsupportedFeature):
        run(V1_DEVICE, lambda d: d.set_zone_brightness(50))


def test_video_brightness_edges_on_reference_device():
    _, frames = run(REFERENCE, lambda d: d.set_video_brightness(40))
    assert frames[0].startswith("33ae010428282828")


def test_video_brightness_whole_screen_on_newer_frk():
    info = device_info("1.10.04", "3.03.01", "1.00.29", "1.03.00")
    _, frames = run(info, lambda d: d.set_video_brightness(40))
    assert frames[0].startswith("33a9020128")


def test_video_brightness_unsupported_and_forced():
    with pytest.raises(UnsupportedFeature):
        run(OLD_FRK, lambda d: d.set_video_brightness(40))

    _, frames = run(OLD_FRK, lambda d: d.set_video_brightness(40, force=True))
    assert frames[0].startswith("33a9020128")


def test_video_brightness_telink_resends_video_frame():
    # reply to the mode read: video, all, game, saturation 70, sound on, softness 30
    replies = {0x05: [0x00, 1, 1, 70, 1, 30, 50]}
    _, frames = run(V1_DEVICE, lambda d: d.set_video_brightness(80), replies)
    assert frames[-1].startswith("330500010146011e50")


def test_video_mode_brightness_goes_in_frame_only_on_telink():
    _, frames = run(V1_DEVICE, lambda d: d.set_video_mode(brightness=60))
    assert frames[0].startswith("33050001003200323c")

    _, frames = run(REFERENCE, lambda d: d.set_video_mode(brightness=60))
    assert frames[0].startswith("330500010032003200")
    assert frames[1].startswith("33ae01043c3c3c3c")


def test_white_balance_gated():
    with pytest.raises(UnsupportedFeature):
        run(OLD_FRK, lambda d: d.set_white_balance_raw(WhiteBalance(True)))

    _, frames = run(
        REFERENCE, lambda d: d.set_white_balance_raw(WhiteBalance(False, 1, 2))
    )
    assert frames[0].startswith("33a9000301" + "0102")

    with pytest.raises(ValueError):
        run(REFERENCE, lambda d: d.set_white_balance_raw(WhiteBalance(False, 100, 50)))


def zone_reply(frame):
    group = frame[2]
    return [group] + [b for slot in range(4) for b in (50 + slot, group, slot, 9)]


def test_mode_read_sends_selector():
    _, frames = run(REFERENCE, lambda d: d.get_mode(), {0x05: [0x13, 4]})
    assert frames[0].startswith("aa0501")


def test_static_mode_reads_zone_colors():
    replies = {0x05: [0x15, 0x01], 0xA5: zone_reply}
    mode, frames = run(REFERENCE, lambda d: d.get_mode(include_zones=True), replies)

    assert isinstance(mode, StaticColorMode)
    assert mode.kind is ColorKind.COLOR
    assert len(mode.zones) == 15
    assert mode.zones[5] == (51, (2, 1, 9))
    assert len(frames) == 5  # mode + 4 groups


def test_static_mode_without_zones():
    mode, frames = run(
        REFERENCE, lambda d: d.get_mode(include_zones=False), {0x05: [0x15, 0x02]}
    )
    assert mode.kind is ColorKind.ZONE_BRIGHTNESS and mode.zones is None
    assert len(frames) == 1


def test_v1_static_mode_reads_legacy_zones():
    replies = {0x05: [0x0B], 0xA2: lambda f: [f[2]] + [f[2], 2, 3] * 4}
    mode, frames = run(V1_DEVICE, lambda d: d.get_mode(include_zones=True), replies)

    assert isinstance(mode, StaticColorMode) and mode.kind is None
    assert mode.zones[0] == (100, (1, 2, 3))
    assert frames[1].startswith("aaa201")


def test_wifi_and_mac_commands():
    _, frames = run(
        REFERENCE,
        lambda d: d.get_mac_address(),
        {0x14: [0xD4, 0xAD, 0xFC, 0xDF, 0xC3, 0x1E]},
    )
    assert frames[0].startswith("aa14")


def test_device_info_reads_wifi_versions():
    replies = {
        0x06: list(b"1.10.04"),
        0x07: [3, *b"3.02.01"],
        0x20: list(b"1.03.00\0"),
        0x21: list(b"1.00.30\0"),
        0xEF: [0, 2, 1],
    }

    async def go(d):
        return await d.get_device_info()

    info, frames = run(None, go, replies)
    assert info.wifi_hard == Version(1, 3, 0) and info.wifi_soft == Version(1, 0, 30)
    assert "aa20" in [f[:4] for f in frames] and "aa21" in [f[:4] for f in frames]


def test_edge_brightness_and_gradient_reads():
    replies = {0xAE: [1, 4, 100, 90, 80, 1], 0xA3: [1]}
    edges, frames = run(REFERENCE, lambda d: d.get_video_edge_brightness(), replies)
    assert tuple(edges) == (100, 90, 80, 1)
    assert frames[0].startswith("aaae01")

    on, _ = run(REFERENCE, lambda d: d.get_gradient(), replies)
    assert on is True


def test_default_white_balance_is_in_range():
    _, frames = run(REFERENCE, lambda d: d.set_white_balance_raw(WhiteBalance(True)))
    assert frames[0].startswith("33a900030010" + "03")


def wb_reply(frame):
    # [type, length, defAuto, defR, defB, manual, R, B]
    return [0, 6, 1, 16, 3, 1, 12, 7]


def test_white_balance_state_and_step():
    state, _ = run(REFERENCE, lambda d: d.get_white_balance(), {0xA9: wb_reply})
    assert state.current == WhiteBalance(False, 12, 7)
    assert state.current.step == 7
    assert state.default == (16, 3)
    assert WhiteBalance(False, 11, 11).step is None


def test_white_balance_steps_cover_table():
    assert len(WHITE_BALANCE_STEPS) == 20
    for step in range(1, 21):
        assert WhiteBalance.from_step(step).step == step

    with pytest.raises(ValueError):
        WhiteBalance.from_step(0)
    with pytest.raises(ValueError):
        WhiteBalance.from_step(21)


def test_set_white_balance_step_20_sends_21_5():
    _, frames = run(REFERENCE, lambda d: d.set_white_balance(20))
    assert frames[0].startswith("33a900030115" + "05")


def test_white_balance_auto_keeps_stored_pair():
    _, frames = run(REFERENCE, lambda d: d.set_white_balance_auto(), {0xA9: wb_reply})
    assert frames[-1].startswith("33a90003" + "00" + "0c07")


def test_white_balance_reset_writes_device_default():
    _, frames = run(REFERENCE, lambda d: d.reset_white_balance(), {0xA9: wb_reply})
    assert frames[-1].startswith("33a90003" + "01" + "1003")


def test_white_balance_limits():
    for bad in (
        WhiteBalance(False, 0, 5),
        WhiteBalance(False, 32, 5),
        WhiteBalance(False, 5, 32),
    ):
        with pytest.raises(ValueError):
            run(REFERENCE, lambda d, bad=bad: d.set_white_balance_raw(bad))

    run(REFERENCE, lambda d: d.set_white_balance_raw(WhiteBalance(False, 31, 31)))


def notification(note_id, *payload):
    return make_frame(0xEE, note_id, list(payload))


def test_notification_is_not_taken_for_a_reply():
    # 0xEE 0x20 (brightness changed) has the id of the WiFi hardware version read
    replies = {0x20: list(b"1.03.00\0")}
    version, _ = run(
        REFERENCE,
        lambda d: d.transport.send_command(GetWifiHardwareVersion()),
        replies,
        unsolicited=[notification(0x20, 77)],
    )
    assert version == "1.03.00"


def test_listener_gets_events():
    events = []

    async def action(device):
        device.add_listener(events.append)
        await device.get_power()

    pushed = [
        notification(0x20, 55),
        notification(0x30, 0, 1),
        notification(0x30, 0, 0),
        notification(0x11, 0),
        notification(0x60, 1, 1),
        notification(0x60, 0, 1),
        notification(0x77, 9),
    ]
    run(REFERENCE, action, {0x01: [1]}, unsolicited=pushed)

    assert events[:5] == [
        BrightnessChanged(55),
        PowerChanged(True),
        PowerChanged(False),
        WifiStateChanged(True),
        MovieModeChanged(True),
    ]
    assert isinstance(events[5], UnknownNotification)
    assert events[6] == UnknownNotification(0x77, events[6].payload)


def test_v1_brightness_event_is_scaled():
    events = []

    async def action(device):
        await device.get_capabilities()  # learn it is V1
        device.add_listener(events.append)
        await device.get_power()

    run(V1_DEVICE, action, {0x01: [1]}, unsolicited=[notification(0x20, 127)])
    assert events == [BrightnessChanged(50)]


def test_listener_errors_do_not_break_commands():
    def bad(_):
        raise RuntimeError("boom")

    async def action(device):
        device.add_listener(bad)
        return await device.get_power()

    power, _ = run(REFERENCE, action, {0x01: [1]}, unsolicited=[notification(0x20, 1)])
    assert power is True


def test_keep_alive_reads_power_when_idle():
    async def idle(device):
        await asyncio.sleep(0.35)

    _, frames = run(REFERENCE, idle, {0x01: [1]}, keep_alive_interval=0.1)
    assert sum(f.startswith("aa01") for f in frames) >= 2


def test_keep_alive_can_be_disabled():
    async def idle(device):
        await asyncio.sleep(0.3)

    _, frames = run(REFERENCE, idle, keep_alive_interval=None)
    assert frames == []


def test_keep_alive_skipped_while_busy():
    async def busy(device):
        for _ in range(6):
            await device.get_brightness()
            await asyncio.sleep(0.05)

    _, frames = run(REFERENCE, busy, {0x04: [50]}, keep_alive_interval=0.2)
    assert not any(f.startswith("aa01") for f in frames)


def black_reply(enabled=1, mode=2, low=10, same=300):
    return [
        0x0A,
        6,
        enabled,
        mode,
        *low.to_bytes(2, "little"),
        *same.to_bytes(2, "little"),
    ]


def test_black_screen_frame():
    setting = BlackScreenSetting(True, BlackScreenMode.SAME_TONE, 45, 600)
    _, frames = run(REFERENCE, lambda d: d.set_black_screen(setting))
    assert frames[0].startswith("33a90a0601" + "02" + "2d00" + "5802")


def test_black_screen_read_parses_mode_and_durations():
    setting, frames = run(
        REFERENCE, lambda d: d.get_black_screen(), {0xA9: black_reply(1, 1, 30, 900)}
    )
    assert setting == BlackScreenSetting(True, BlackScreenMode.LOW_BRIGHTNESS, 30, 900)
    assert frames[0].startswith("aaa90a")

    # anything but 1 is same tone
    setting, _ = run(
        REFERENCE, lambda d: d.get_black_screen(), {0xA9: black_reply(0, 7)}
    )
    assert setting.mode is BlackScreenMode.SAME_TONE and not setting.enabled


def test_black_screen_update_keeps_other_fields():
    replies = {0xA9: black_reply(1, 2, 20, 600)}
    _, frames = run(
        REFERENCE,
        lambda d: d.update_black_screen(mode=BlackScreenMode.LOW_BRIGHTNESS),
        replies,
    )
    assert frames[-1].startswith("33a90a0601" + "01" + "1400" + "5802")


def test_black_screen_update_rejects_invalid_stored_durations():
    replies = {0xA9: black_reply(1, 1, 0, 0)}
    with pytest.raises(ValueError):
        run(REFERENCE, lambda d: d.update_black_screen(enabled=False), replies)


def test_black_screen_validates_and_is_gated():
    with pytest.raises(ValueError):
        run(
            REFERENCE,
            lambda d: d.set_black_screen(
                BlackScreenSetting(True, BlackScreenMode.SAME_TONE, 10, 60)
            ),
        )

    with pytest.raises(UnsupportedFeature):
        run(OLD_FRK, lambda d: d.get_black_screen())


def test_color_temperature_frame_v2():
    kelvin, frames = run(REFERENCE, lambda d: d.set_color_temperature(4000))
    assert kelvin == 4000
    # FF FF FF, 4000 K = 0x0FA0, tint FFD5A1, all zones
    assert frames[0].startswith("33051501ffffff0fa0ffd5a1ff7f")


def test_color_temperature_snaps_and_limits():
    assert run(REFERENCE, lambda d: d.set_color_temperature(6700))[0] == 6500
    assert run(REFERENCE, lambda d: d.set_color_temperature(4550))[0] == 4500
    assert run(REFERENCE, lambda d: d.set_color_temperature(9000))[0] == 9000

    for bad in (1999, 9001):
        with pytest.raises(ValueError):
            run(REFERENCE, lambda d, bad=bad: d.set_color_temperature(bad))


def test_color_temperature_zones_and_v1():
    _, frames = run(REFERENCE, lambda d: d.set_color_temperature(2000, [0, 14]))
    assert frames[0].startswith("33051501ffffff07d0ff8d0b0140")

    # V1: tint as RGB, then kelvin, then the mask
    _, frames = run(V1_DEVICE, lambda d: d.set_color_temperature(9000))
    assert frames[0].startswith("33050bd9e1ff2328ff7f")


def test_v1_plain_color_gets_kelvin_from_table():
    # in the table: FFD5A1 is 4000 K
    _, frames = run(V1_DEVICE, lambda d: d.set_static_color((0xFF, 0xD5, 0xA1)))
    assert frames[0].startswith("33050bffd5a10fa0ff7f")

    # not in the table: 2000 K
    _, frames = run(V1_DEVICE, lambda d: d.set_static_color((1, 2, 3)))
    assert frames[0].startswith("33050b01020307d0ff7f")


def test_zone_state_kelvin_reverse_lookup():
    from govee_h6199_ble import ZoneState

    assert ZoneState(100, (0xFF, 0xD5, 0xA1)).kelvin == 4000
    assert ZoneState(100, (0xFF, 0xD1, 0xA3)).kelvin == 4000  # second column
    assert ZoneState(100, (1, 2, 3)).kelvin is None
