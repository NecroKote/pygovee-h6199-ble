import asyncio
from dataclasses import FrozenInstanceError

import pytest
from bleak.exc import BleakError
from test_device import (
    OLD_FRK,
    REFERENCE,
    V1_DEVICE,
    FakeClient,
    black_reply,
    run,
    wb_reply,
)

import govee_h6199_ble as g
from govee_h6199_ble.protocol.commands import GetPowerState, GetWifiHardwareVersion


class SilentClient(FakeClient):
    async def write_gatt_char(self, _, frame, response=False):
        self.frames.append(frame)


class BrokenClient(FakeClient):
    async def write_gatt_char(self, _, frame, response=False):
        raise BleakError("link lost")


class SlowWriter(SilentClient):
    async def write_gatt_char(self, _, frame, response=False):
        await asyncio.Future()


def test_explicit_exports_and_aliases():
    assert all(hasattr(g, name) for name in g.__all__)
    assert not hasattr(g, "dataclass")
    assert not hasattr(g, "NamedTuple")
    assert g.MusicMode.RYTHM is g.MusicMode.RHYTHM
    assert g.UnknownColorMode(99).mode == g.UnknownColorMode(99).raw_mode == 99
    assert g.__version__


def test_results_are_immutable():
    mode, frames = run(REFERENCE, lambda d: d.get_mode(), {5: [0x15, 1]})
    assert len(frames) == 1 and mode.zones is None
    with pytest.raises(FrozenInstanceError):
        mode.kind = None
    mode, _ = run(
        REFERENCE,
        lambda d: d.get_mode(True),
        {5: [0x15, 1], 0xA5: lambda f: [f[2]] + [50, 1, 2, 3] * 4},
    )
    assert isinstance(mode.zones, tuple)


def test_before_start_and_after_stop_fail_promptly():
    async def go():
        device = g.GoveeH6199(
            FakeClient(), device_info=REFERENCE, keep_alive_interval=None
        )
        with pytest.raises(g.NotStarted):
            await device.get_power()
        await device.start()
        await device.stop()
        with pytest.raises(g.NotStarted):
            await device.get_power()

    asyncio.run(go())


@pytest.mark.parametrize(
    "client,timeouts",
    [
        (SilentClient, g.CommandTimeouts(response=0.001)),
        (SlowWriter, g.CommandTimeouts(write=0.001)),
    ],
)
def test_timeouts_are_library_errors_and_clear_pending(client, timeouts):
    async def go():
        device = g.GoveeH6199(
            client(), device_info=REFERENCE, timeouts=timeouts, keep_alive_interval=None
        )
        async with device:
            for _ in range(2):
                with pytest.raises(g.CommandTimeout) as caught:
                    await device.set_power(True)
                assert isinstance(caught.value, g.GoveeError)
                assert isinstance(caught.value.__cause__, TimeoutError)
                assert device.transport._pending_future is None

    asyncio.run(go())


def test_transport_none_uses_default_deadline_and_suppresses_timeout(monkeypatch):
    async def go():
        transport = g.Transport(SilentClient())
        seen = []

        async def expire(frame, timeouts):
            seen.append(timeouts)
            raise g.CommandTimeout()

        monkeypatch.setattr(transport, "exchange_frame", expire)
        assert await transport.send_command(GetPowerState(), None) is None
        assert seen == [g.CommandTimeouts()]

    asyncio.run(go())


def test_disconnect_event_and_error_are_emitted_once():
    async def go():
        device = g.GoveeH6199(
            BrokenClient(), device_info=REFERENCE, keep_alive_interval=None
        )
        events = []
        device.add_listener(events.append)
        async with device:
            with pytest.raises(g.TransportError) as caught:
                await device.get_power()
            assert isinstance(caught.value.__cause__, BleakError)
            with pytest.raises(g.NotStarted):
                await device.get_power()
        assert events == [g.Disconnected("link lost")]

    asyncio.run(go())


def test_keep_alive_surfaces_disconnect():
    async def go():
        device = g.GoveeH6199(
            BrokenClient(), device_info=REFERENCE, keep_alive_interval=0.001
        )
        event = asyncio.get_running_loop().create_future()
        device.add_listener(lambda result: event.set_result(result))
        async with device:
            assert isinstance(await asyncio.wait_for(event, 1), g.Disconnected)

    asyncio.run(go())


def test_listener_and_notification_removal_is_idempotent():
    device = g.GoveeH6199(FakeClient(), keep_alive_interval=None)
    events = []
    for add in [device.add_listener, device.transport.add_notification_handler]:
        remove = add(events.append)
        remove()
        remove()
    device._handle_notification(0x20, b"\x32")
    assert events == []


def test_malformed_response_is_library_error():
    async def action(device):
        await device.transport.send_command(GetWifiHardwareVersion())

    with pytest.raises(g.InvalidResponse) as caught:
        run(REFERENCE, action, {0x20: list(b"bad")})
    assert isinstance(caught.value.__cause__, ValueError)


def test_info_does_not_hide_optional_parse_failures():
    replies = {6: list(b"1.10.04"), 7: [3, *b"3.02.01"], 0x21: list(b"bad")}
    with pytest.raises(g.InvalidResponse):
        run(None, lambda d: d.get_device_info(), replies)


def test_optional_deadline_is_configurable_and_warns(caplog):
    class PartialClient(FakeClient):
        async def write_gatt_char(self, characteristic, frame, response=False):
            if frame[1] in (0x20, 0x21, 0xEF):
                return
            await super().write_gatt_char(characteristic, frame, response=response)

    async def go():
        client = PartialClient({6: list(b"1.10.04"), 7: [3, *b"3.02.01"]})
        async with g.GoveeH6199(
            client, optional_response_timeout=0.001, keep_alive_interval=None
        ) as device:
            info = await device.get_device_info()
            assert info.pact is None and info.wifi_soft is None
            assert not (await device.get_capabilities()).zone_brightness

    asyncio.run(go())
    assert "capability inputs incomplete" in caplog.text
    assert "protocol generation unknown" in caplog.text


def test_capability_refresh_and_version_types():
    replies = {
        6: list(b"1.10.04"),
        7: [3, *b"3.02.01"],
        0x21: list(b"1.00.30"),
        0x20: list(b"1.03.00"),
        0xEF: [0, 4, 1],
    }

    async def action(device):
        assert not (await device.get_capabilities()).video_segment_brightness
        assert (await device.get_capabilities(refresh=True)).video_segment_brightness
        assert await device.get_firmware_version() == g.Version(1, 10, 4)
        assert await device.get_hardware_version() == g.Version(3, 2, 1)

    run(OLD_FRK, action, replies)


@pytest.mark.parametrize(
    "action",
    [
        lambda d: d.set_zone_brightness(50, force=True),
        lambda d: d.set_zone_brightnesses([50] * 15, force=True),
        lambda d: d.set_white_balance_auto(force=True),
        lambda d: d.reset_white_balance(force=True, auto=True),
        lambda d: d.get_white_balance(force=True),
        lambda d: d.get_black_screen(force=True),
        lambda d: d.update_black_screen(enabled=False, force=True),
        lambda d: d.get_video_edge_brightness(force=True),
        lambda d: d.set_video_edge_brightness(
            left=1, top=2, right=3, bottom=4, force=True
        ),
        lambda d: d.get_video_brightness(force=True),
        lambda d: d.set_video_mode(brightness=50, force=True),
    ],
)
def test_force_bypasses_gates_on_reads_and_writes(action):
    def reply(frame):
        if frame[2] == 0x0A:
            return black_reply()
        return wb_reply(frame)

    run(OLD_FRK, action, {0xA9: reply, 0xAE: [1, 4, 1, 2, 3, 4]})


def test_forced_zone_brightness_uses_modern_frame_on_v1():
    _, frames = run(V1_DEVICE, lambda d: d.set_zone_brightness(40, force=True))
    assert frames[0].startswith("3305150228ff7f")


def test_video_brightness_getters_follow_firmware():
    edges, _ = run(
        REFERENCE, lambda d: d.get_video_brightness(), {0xAE: [1, 4, 10, 20, 30, 40]}
    )
    assert edges == g.EdgeBrightness(10, 20, 30, 40)
    percent, _ = run(
        V1_DEVICE, lambda d: d.get_video_brightness(), {5: [0, 1, 0, 50, 0, 50, 80]}
    )
    assert percent == 80
    with pytest.raises(g.UnsupportedFeature):
        run(V1_DEVICE, lambda d: d.get_video_brightness(), {5: [0x15, 1]})
    with pytest.raises(g.InvalidResponse):
        run(V1_DEVICE, lambda d: d.get_video_brightness(), {5: [0, 1, 0, 50, 0, 50, 0]})


def test_video_mode_brightness_gated_before_any_write():
    client = FakeClient()

    async def go():
        async with g.GoveeH6199(
            client, device_info=OLD_FRK, keep_alive_interval=None
        ) as device:
            with pytest.raises(g.UnsupportedFeature):
                await device.set_video_mode(brightness=50)
        assert client.frames == []

    asyncio.run(go())


def test_telink_unspecified_parameters_use_write_defaults():
    _, frames = run(
        V1_DEVICE, lambda d: d.set_video_brightness(80), {5: [0, 1, 0, 0, 0, 0, 0]}
    )
    assert frames[-1].startswith("330500010032003250")


def test_mode_convenience_getters():
    assert run(REFERENCE, lambda d: d.get_video_mode(), {5: [0x13, 3]})[0] is None
    assert run(REFERENCE, lambda d: d.get_music_mode(), {5: [0x13, 3]})[
        0
    ] == g.MusicColorMode(g.MusicMode.RHYTHM)


def test_concurrent_white_balance_write_cannot_interrupt_read_modify_write():
    _, frames = run(
        REFERENCE,
        lambda d: asyncio.gather(d.set_white_balance_auto(), d.set_white_balance(20)),
        {0xA9: wb_reply},
    )
    assert [f[:4] for f in frames] == ["aaa9", "33a9", "33a9"]
    assert frames[1].startswith("33a90003000c07")
    assert frames[2].startswith("33a90003011505")


def test_concurrent_black_screen_updates_keep_both_changes():
    setting = g.BlackScreenSetting(True)

    def reply(frame):
        nonlocal setting
        if frame[0] == 0x33:
            from govee_h6199_ble.protocol.commands import GetBlackScreen

            setting = GetBlackScreen().parse_response(frame[2:19])
        return black_reply(
            setting.enabled,
            setting.mode,
            setting.low_brightness_seconds,
            setting.same_tone_seconds,
        )

    run(
        REFERENCE,
        lambda d: asyncio.gather(
            d.update_black_screen(enabled=False),
            d.update_black_screen(same_tone_seconds=600),
        ),
        {0xA9: reply},
    )
    assert not setting.enabled and setting.same_tone_seconds == 600


def test_reset_white_balance_can_choose_auto():
    _, frames = run(
        REFERENCE, lambda d: d.reset_white_balance(auto=True), {0xA9: wb_reply}
    )
    assert frames[-1].startswith("33a90003001003")


def test_static_color_accepts_lists_and_zones():
    _, frames = run(REFERENCE, lambda d: d.set_static_color([1, 2, 3], zones=[14]))
    assert frames[0].startswith("3305150101020300000000000040")


def test_connected_forwards_constructor_options():
    async def go():
        async with g.connected(
            FakeClient(),
            device_info=REFERENCE,
            keep_alive_interval=None,
            optional_response_timeout=0.1,
        ) as device:
            assert await device.get_device_info() == REFERENCE
            assert device._keep_alive_task is None
            assert device._optional_response_timeout == 0.1

    asyncio.run(go())


def test_stop_and_cancellation_release_pending_commands():
    async def go():
        client = SilentClient()
        transport = g.Transport(client)
        await transport.start()
        pending = asyncio.create_task(transport.send_command(GetPowerState()))
        while not client.frames:
            await asyncio.sleep(0)
        await transport.stop()
        with pytest.raises(g.NotStarted):
            await pending
        await transport.start()
        pending = asyncio.create_task(transport.send_command(GetPowerState()))
        while len(client.frames) < 2:
            await asyncio.sleep(0)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert transport._pending_future is None
        await transport.stop()

    asyncio.run(go())


@pytest.mark.parametrize(
    "action",
    [
        lambda d: d.set_zone_brightness(50),
        lambda d: d.set_zone_brightnesses([50] * 15),
        lambda d: d.get_white_balance(),
        lambda d: d.set_white_balance(1),
        lambda d: d.set_white_balance_raw(g.WhiteBalance(True)),
        lambda d: d.set_white_balance_auto(),
        lambda d: d.reset_white_balance(),
        lambda d: d.get_black_screen(),
        lambda d: d.set_black_screen(g.BlackScreenSetting(True)),
        lambda d: d.update_black_screen(enabled=False),
        lambda d: d.get_video_edge_brightness(),
        lambda d: d.set_video_edge_brightness(left=1, top=2, right=3, bottom=4),
        lambda d: d.get_video_brightness(),
        lambda d: d.set_video_brightness(50),
        lambda d: d.set_video_mode(brightness=50),
    ],
)
def test_gated_methods_reject_before_sending_with_one_message(action):
    info = g.DeviceInfo(g.Version(1), g.Version(3), pact=g.Pact(1, 1))
    client = FakeClient()

    async def go():
        async with g.GoveeH6199(
            client, device_info=info, keep_alive_interval=None
        ) as device:
            with pytest.raises(g.UnsupportedFeature) as caught:
                await action(device)
            assert caught.value.reason == "not enabled by device capabilities"
            assert client.frames == []

    asyncio.run(go())


def test_timeout_identifies_write_and_response_phases():
    async def go():
        for client, timeouts, phase in [
            (SilentClient(), g.CommandTimeouts(response=0.001), "response"),
            (SlowWriter(), g.CommandTimeouts(write=0.001), "write"),
        ]:
            async with g.GoveeH6199(
                client, timeouts=timeouts, keep_alive_interval=None
            ) as device:
                with pytest.raises(g.CommandTimeout) as caught:
                    await device.get_power()
                assert caught.value.phase == phase

    asyncio.run(go())


def test_start_failures_use_library_errors():
    async def go():
        for error, expected in [
            (BleakError("start failed"), g.TransportError),
            (TimeoutError(), g.CommandTimeout),
        ]:

            class CannotStart(FakeClient):
                async def start_notify(self, _, callback, error=error):
                    raise error

            device = g.GoveeH6199(CannotStart(), keep_alive_interval=None)
            with pytest.raises(expected) as caught:
                await device.start()
            assert caught.value.__cause__ is error

    asyncio.run(go())


def test_restarting_after_failed_keep_alive_starts_new_worker():
    class RecoverableClient(FakeClient):
        broken = True

        async def write_gatt_char(self, characteristic, frame, response=False):
            if self.broken:
                raise BleakError("link lost")
            await super().write_gatt_char(characteristic, frame, response=response)

    async def go():
        client = RecoverableClient()
        device = g.GoveeH6199(client, device_info=REFERENCE, keep_alive_interval=0.001)
        try:
            await device.start()
            old_worker = device._keep_alive_task
            await asyncio.wait_for(old_worker, 1)
            client.broken = False
            await device.start()
            assert device._keep_alive_task is not old_worker
            assert not device._keep_alive_task.done()
        finally:
            await device.stop()

    asyncio.run(go())


def test_optional_reads_do_not_suppress_write_timeouts():
    class BadOptionalWrite(FakeClient):
        async def write_gatt_char(self, characteristic, frame, response=False):
            if frame[1] == 0x21:
                await asyncio.Future()
            else:
                await super().write_gatt_char(characteristic, frame, response=response)

    async def go():
        client = BadOptionalWrite({6: list(b"1.10.04"), 7: [3, *b"3.02.01"]})
        async with g.GoveeH6199(
            client, timeouts=g.CommandTimeouts(write=0.001), keep_alive_interval=None
        ) as device:
            with pytest.raises(g.CommandTimeout) as caught:
                await device.get_device_info()
            assert caught.value.phase == "write"

    asyncio.run(go())


def test_corrupt_reply_is_invalid_response():
    class CorruptClient(FakeClient):
        async def write_gatt_char(self, _, frame, response=False):
            self._callback(None, bytearray([0xAA, frame[1], 1]))

    async def go():
        async with g.GoveeH6199(CorruptClient(), keep_alive_interval=None) as device:
            with pytest.raises(g.InvalidResponse) as caught:
                await device.get_power()
            assert isinstance(caught.value.__cause__, ValueError)

    asyncio.run(go())


def test_unknown_pact_does_not_enable_zone_brightness():
    for pact in [None, g.Pact(9, 1), g.Pact(2, 2)]:
        info = g.DeviceInfo(g.Version(1, 10, 4), g.Version(3, 2, 1), pact=pact)
        assert not g.Capabilities.from_info(info).zone_brightness


def test_state_snapshot_uses_immutable_zones():
    replies = {
        1: [1],
        4: [50],
        5: [0x15, 1],
        0xA5: lambda f: [f[2]] + [50, 1, 2, 3] * 4,
    }
    state, _ = run(REFERENCE, lambda d: d.read_state(), replies)
    assert isinstance(state.zones, tuple) and len(state.zones) == 15
    assert state.mode.zones is None
    with pytest.raises(FrozenInstanceError):
        state.brightness = 1


def test_concurrent_telink_video_writes_do_not_interleave():
    _, frames = run(
        V1_DEVICE,
        lambda d: asyncio.gather(
            d.set_video_brightness(80), d.set_video_mode(saturation=20)
        ),
        {5: [0, 1, 0, 50, 0, 50, 60]},
    )
    assert [f[:4] for f in frames] == ["aa05", "3305", "3305"]
    assert frames[1].startswith("330500010032003250")
    assert frames[2].startswith("3305000100140032")
