import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable, Iterable, Mapping, Sequence, TypeVar

from bleak import BleakClient

from .capabilities import Capabilities, ChipFamily, DeviceInfo, Version, from_info
from .errors import UnsupportedFeature
from .events import BrightnessChanged, DeviceEvent, parse_notification
from .model import (
    BlackScreenMode,
    BlackScreenSetting,
    DeviceState,
    EdgeBrightness,
    Modes,
    Pact,
    RGBColor,
    StaticColorMode,
    VideoColorMode,
    WhiteBalance,
    WhiteBalanceState,
    ZoneState,
)
from .profiles import ColorProfile, ColorProfileV1, color_profile
from .protocol.base import Command, CommandWithParser
from .protocol.commands import (
    GetBlackScreen,
    GetColorMode,
    GetGradient,
    GetFirmwareVersion,
    GetHardwareVersion,
    GetMacAddress,
    GetPact,
    GetPowerState,
    GetVideoEdgeBrightness,
    GetWhiteBalance,
    GetWholeScreenBrightness,
    GetWifiFirmwareVersion,
    GetWifiHardwareVersion,
    PowerOff,
    PowerOn,
    SetBlackScreen,
    SetGradient,
    SetMusicModeEnergic,
    SetMusicModeRolling,
    SetMusicModeRythm,
    SetMusicModeSpectrum,
    SetVideoEdgeBrightness,
    SetVideoMode,
    SetWhiteBalance,
    SetWholeScreenBrightness,
)
from .protocol.colortemp import nearest_color_temperature
from .protocol.const import ZONE_COUNT, MusicMode
from .transport import CommandTimeouts, Transport


T = TypeVar("T")


class GoveeH6199:
    """
    Govee DreamView T1 (H6199).

    High level interface: methods take plain values and pick the right frames
    for the connected firmware. Raw frame access is available as `transport`.
    """

    def __init__(
        self,
        client: BleakClient,
        logger: logging.Logger | None = None,
        device_info: DeviceInfo | None = None,
        timeouts: CommandTimeouts = CommandTimeouts(),
        keep_alive_interval: float | None = 5.0,
    ):
        """
        :param device_info: versions of the device, if already known. Saves
            the reads on first use of a version dependent feature.
        :param timeouts: used by every call that doesn't take its own
        :param keep_alive_interval: seconds of silence after which a power
            read is sent while started. The device drops an idle connection
            after about 10 s, which also ends `add_listener` events. `None`
            turns it off.
        """

        self._log = logger or logging.getLogger(__name__ + "@" + str(id(self)))
        self._transport = Transport(client, self._log)
        self._transport.add_notification_handler(self._handle_notification)
        self._listeners: list[Callable[[DeviceEvent], None]] = []
        self._timeouts = timeouts
        self._keep_alive_interval = keep_alive_interval
        self._keep_alive_task: asyncio.Task | None = None
        self._info = device_info
        self._capabilities: Capabilities | None = None

    @property
    def transport(self) -> Transport:
        """Raw access: send arbitrary commands and frames"""
        return self._transport

    def add_listener(
        self, listener: Callable[[DeviceEvent], None]
    ) -> Callable[[], None]:
        """
        Be called with a `DeviceEvent` whenever the device reports a change on
        its own (power, brightness, ...), e.g. when it is controlled by another client or a remote.

        The listener runs in the event loop and must not block. Returns a
        function that removes the listener.
        """

        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def _handle_notification(self, notification_id: int, payload: bytes):
        event = parse_notification(notification_id, payload)

        if isinstance(event, BrightnessChanged) and self._capabilities is not None:
            if self._capabilities.legacy_color:
                scale = ColorProfileV1.BRIGHTNESS_SCALE
                event = BrightnessChanged(min(100, round(event.brightness * 100 / scale)))

        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                self._log.exception("listener failed")

    async def start(self):
        await self._transport.start()

        if self._keep_alive_interval and self._keep_alive_task is None:
            self._keep_alive_task = asyncio.create_task(self._keep_alive())

    async def stop(self):
        if self._keep_alive_task is not None:
            self._keep_alive_task.cancel()
            await asyncio.gather(self._keep_alive_task, return_exceptions=True)
            self._keep_alive_task = None

        await self._transport.stop()

    async def _keep_alive(self):
        interval = self._keep_alive_interval
        while True:
            idle = time.monotonic() - self._transport.last_activity
            await asyncio.sleep(max(0.0, interval - idle))

            if time.monotonic() - self._transport.last_activity < interval:
                continue

            try:
                await self._send(GetPowerState())
            except asyncio.TimeoutError:
                self._log.debug("keep-alive not answered")
            except Exception:
                self._log.debug("keep-alive failed, stopping", exc_info=True)
                return

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.stop()

    async def get_device_info(self, refresh: bool = False) -> DeviceInfo:
        """
        Versions of the device. Read once, then cached.

        The WiFi versions and the pact are optional: if the device doesn't
        answer, they are left empty.
        """

        if self._info is not None and not refresh:
            return self._info

        send = lambda command: self._transport.send_command(command, self._timeouts)

        soft = Version.parse(await send(GetFirmwareVersion()))
        hard = Version.parse(await send(GetHardwareVersion()))

        async def optional(command):
            try:
                # silent devices should not stall the first call for long
                return await self._transport.send_command(
                    command, CommandTimeouts(self._timeouts.write, 2.0)
                )
            except (asyncio.TimeoutError, ValueError):
                self._log.debug(f"{command} not answered")
                return None

        wifi_soft = await optional(GetWifiFirmwareVersion())
        wifi_hard = await optional(GetWifiHardwareVersion())

        self._info = DeviceInfo(
            soft=soft,
            hard=hard,
            wifi_soft=Version.parse(wifi_soft) if wifi_soft else None,
            wifi_hard=Version.parse(wifi_hard) if wifi_hard else None,
            pact=await optional(GetPact()),
        )
        self._capabilities = None

        return self._info

    async def get_capabilities(self) -> Capabilities:
        """What the device supports. Read once, then cached."""

        if self._capabilities is None:
            self._capabilities = from_info(await self.get_device_info())

        return self._capabilities

    async def _send(self, command: CommandWithParser[T] | Command):
        return await self._transport.send_command(command, self._timeouts)

    async def _profile(self) -> ColorProfile:
        return color_profile(await self.get_capabilities())

    @staticmethod
    def _require(feature: str, supported: bool, reason: str, force: bool = False):
        if not supported and not force:
            raise UnsupportedFeature(feature, reason)

    # --- info -------------------------------------------------------------

    async def get_firmware_version(self) -> str:
        return await self._send(GetFirmwareVersion())

    async def get_hardware_version(self) -> str:
        return await self._send(GetHardwareVersion())

    async def get_mac_address(self) -> str:
        """MAC address of the WiFi chip"""
        return await self._send(GetMacAddress())

    async def get_pact(self) -> Pact:
        return await self._send(GetPact())

    # --- power and brightness ---------------------------------------------

    async def get_power(self) -> bool:
        return await self._send(GetPowerState())

    async def set_power(self, on: bool):
        await self._send(PowerOn() if on else PowerOff())

    async def get_brightness(self) -> int:
        """Overall brightness in percent"""
        return await self._send((await self._profile()).get_brightness())

    async def set_brightness(self, percent: int):
        """Overall brightness, 1-100"""
        await self._send((await self._profile()).set_brightness(percent))

    # --- colors and zones -------------------------------------------------

    async def set_static_color(self, color: RGBColor):
        """Switch to the static color mode, all zones in one color"""
        await self._send((await self._profile()).set_zone_color(color, None))

    async def set_color_temperature(
        self, kelvin: int, zones: Iterable[int] | None = None
    ) -> int:
        """
        Switch to the static color mode with a color temperature, 2000-9000 K.

        The protocol's color table only has these values: every 100 K up to
        6500, then 7000, 7200, 8000, 8200, 9000. Any other value is rounded to
        the nearest of them, which is also returned. A value without a table
        entry is never sent, since it would have no tint and turn the lights
        black.

        :param zones: zones to change, all by default
        """

        kelvin = nearest_color_temperature(kelvin)
        await self._send(
            (await self._profile()).set_zone_color_temperature(kelvin, zones)
        )
        return kelvin

    async def set_zone_colors(
        self, colors: Mapping[int, RGBColor] | Sequence[RGBColor]
    ):
        """
        Switch to the static color mode and paint zones 0-14.

        Takes either `{zone: color}` (other zones keep their color) or a
        sequence of exactly 15 colors. Zones of the same color share a frame.
        """

        if not isinstance(colors, Mapping):
            if len(colors) != ZONE_COUNT:
                raise ValueError(f"expected {ZONE_COUNT} colors, got {len(colors)}")
            colors = dict(enumerate(colors))

        by_color: dict[RGBColor, list[int]] = defaultdict(list)
        for zone, color in colors.items():
            by_color[tuple(color)].append(zone)

        profile = await self._profile()
        for color, zones in by_color.items():
            await self._send(profile.set_zone_color(color, zones))

    async def set_zone_brightness(
        self, percent: int, zones: Iterable[int] | None = None
    ):
        """Brightness 1-100 of the given zones (all by default)"""
        await self._send((await self._profile()).set_zone_brightness(percent, zones))

    async def set_zone_brightnesses(self, percents: Sequence[int]):
        """Brightness 1-100 of each of the 15 zones"""
        await self._send((await self._profile()).set_zone_brightness_list(percents))

    async def get_zone_states(self) -> list[ZoneState]:
        """Read color and brightness of all 15 zones (4 requests)."""

        profile = await self._profile()
        states: list[ZoneState] = []
        for group in range(1, 5):
            states += await self._send(profile.get_zone_group(group))

        return states

    async def get_gradient(self) -> bool:
        return await self._send(GetGradient())

    async def set_gradient(self, enabled: bool):
        """Smooth color gradient between zones"""
        await self._send(SetGradient(enabled))

    # --- modes ------------------------------------------------------------

    async def get_mode(self, include_zones: bool = True) -> Modes:
        """
        Current mode.

        In the static color mode the colors are read too (4 more requests),
        unless `include_zones` is off.
        """

        mode = await self._send(GetColorMode())

        if include_zones and isinstance(mode, StaticColorMode):
            mode.zones = await self.get_zone_states()

        return mode

    async def set_music_mode(
        self,
        effect: MusicMode,
        sensitivity: int = 99,
        color: RGBColor | None = None,
        calm: bool = True,
    ):
        """
        Music mode. `color` is ignored by the energic effect, `calm` is only
        used by the rhythm effect.
        """

        match effect:
            case MusicMode.RYTHM:
                command = SetMusicModeRythm(calm, sensitivity, color)
            case MusicMode.ENERGIC:
                command = SetMusicModeEnergic(sensitivity)
            case MusicMode.SPECTRUM:
                command = SetMusicModeSpectrum(sensitivity, color)
            case MusicMode.ROLLING:
                command = SetMusicModeRolling(sensitivity, color)
            case _:
                raise ValueError(f"unknown music effect {effect!r}")

        await self._send(command)

    async def set_video_mode(
        self,
        full_screen: bool = True,
        game_mode: bool = False,
        saturation: int = 50,
        sound_effects: bool = False,
        sound_effects_softness: int = 50,
        brightness: int | None = None,
    ):
        """
        Video (camera) mode.

        :param brightness: 1-100, applied the way the firmware supports it, see
            `set_video_brightness`. Left alone if `None`.
        """

        caps = await self.get_capabilities()
        in_frame = brightness if caps.chip == ChipFamily.TELINK else None

        await self._send(
            SetVideoMode(
                full_screen,
                game_mode,
                saturation,
                sound_effects,
                sound_effects_softness,
                in_frame,
            )
        )

        if brightness is not None and in_frame is None:
            await self.set_video_brightness(brightness)

    async def set_video_brightness(self, percent: int, force: bool = False):
        """
        Video mode brightness, 1-100.

        Uses whatever the firmware has: per-edge brightness, whole-screen
        brightness, or the brightness byte of the video frame (Telink, needs
        the device to be in video mode).

        :param force: send the whole-screen command even if the firmware is not
            known to support any of them
        """

        caps = await self.get_capabilities()

        if caps.video_segment_brightness:
            await self._send(SetVideoEdgeBrightness(percent, percent, percent, percent))
        elif caps.video_brightness and caps.chip == ChipFamily.TELINK:
            mode = await self.get_mode(include_zones=False)
            if not isinstance(mode, VideoColorMode):
                raise UnsupportedFeature(
                    "video brightness", "this firmware needs the video mode active"
                )

            await self._send(
                SetVideoMode(
                    mode.full_screen,
                    mode.game_mode,
                    max(1, mode.saturation),
                    mode.sound_effects,
                    max(1, mode.sound_effects_softness),
                    percent,
                )
            )
        else:
            self._require(
                "video brightness", caps.video_brightness, "firmware too old", force
            )
            await self._send(SetWholeScreenBrightness(percent))

    async def get_video_brightness(self) -> int:
        """Whole-screen video brightness in percent"""

        caps = await self.get_capabilities()
        self._require(
            "video brightness reading",
            caps.video_brightness,
            "not available on this firmware",
        )
        return await self._send(GetWholeScreenBrightness())

    async def set_video_edge_brightness(
        self, left: int, top: int, right: int, bottom: int, force: bool = False
    ):
        """Relative brightness 1-100 of each screen edge in video mode"""

        caps = await self.get_capabilities()
        self._require(
            "edge brightness",
            caps.video_segment_brightness,
            "needs hardware 3.02.01 / 3.02.10 and recent firmware",
            force,
        )
        await self._send(SetVideoEdgeBrightness(left, top, right, bottom))

    async def get_video_edge_brightness(self) -> EdgeBrightness:
        """Relative brightness of each screen edge in video mode"""

        caps = await self.get_capabilities()
        self._require(
            "edge brightness",
            caps.video_segment_brightness,
            "needs hardware 3.02.01 / 3.02.10 and recent firmware",
        )
        return await self._send(GetVideoEdgeBrightness())

    async def get_white_balance(self) -> WhiteBalanceState:
        """Current white balance and the device default red / blue"""

        caps = await self.get_capabilities()
        self._require(
            "white balance", caps.white_balance, "not available on this firmware"
        )
        return await self._send(GetWhiteBalance())

    async def _write_white_balance(self, white_balance: WhiteBalance, force: bool):
        caps = await self.get_capabilities()
        self._require(
            "white balance",
            caps.white_balance,
            "not available on this firmware",
            force,
        )
        await self._send(SetWhiteBalance(white_balance))

    async def set_white_balance_raw(self, white_balance: WhiteBalance, force: bool = False):
        """
        Video mode white balance with explicit red / blue (1-31 each).
        Prefer `set_white_balance`, which uses the 20 defined steps.
        """

        await self._write_white_balance(white_balance, force)

    async def set_white_balance(self, step: int, force: bool = False):
        """Manual white balance, step 1-20 of the defined steps"""

        await self._write_white_balance(WhiteBalance.from_step(step), force)

    async def set_white_balance_auto(self):
        """Automatic white balance. The stored manual red / blue are kept."""

        current = (await self.get_white_balance()).current
        await self._write_white_balance(
            WhiteBalance(True, current.red, current.blue), False
        )

    async def reset_white_balance(self):
        """Write the device's own default red / blue, keeping auto on or off"""

        state = await self.get_white_balance()
        await self._write_white_balance(
            WhiteBalance(state.current.auto, *state.default), False
        )

    async def _require_black_screen(self, force: bool = False):
        caps = await self.get_capabilities()
        self._require(
            "black screen setting",
            caps.black_screen,
            "needs hardware 3.02.01 / 3.02.10 and recent firmware",
            force,
        )

    async def get_black_screen(self) -> BlackScreenSetting:
        """What the device does when the picture goes black in video mode"""

        await self._require_black_screen()
        return await self._send(GetBlackScreen())

    async def set_black_screen(self, setting: BlackScreenSetting, force: bool = False):
        """
        Set all of the black screen setting at once. Durations must be in the
        range the protocol allows, see `BlackScreenSetting.normalized`.
        """

        await self._require_black_screen(force)
        await self._send(SetBlackScreen(setting))

    async def update_black_screen(
        self,
        enabled: bool | None = None,
        mode: BlackScreenMode | None = None,
        low_brightness_seconds: int | None = None,
        same_tone_seconds: int | None = None,
    ):
        """
        Change some fields of the black screen setting and keep the others, as
        both durations are sent every time. A stored duration outside the
        allowed range is replaced by its default.
        """

        current = (await self.get_black_screen()).normalized()
        changes = {
            "enabled": enabled,
            "mode": mode,
            "low_brightness_seconds": low_brightness_seconds,
            "same_tone_seconds": same_tone_seconds,
        }
        changed = current._replace(**{k: v for k, v in changes.items() if v is not None})
        await self._send(SetBlackScreen(changed))

    # --- everything at once -----------------------------------------------

    async def read_state(self) -> DeviceState:
        """Read power, brightness, mode and zones"""

        return DeviceState(
            power=await self.get_power(),
            brightness=await self.get_brightness(),
            mode=await self.get_mode(include_zones=False),
            zones=await self.get_zone_states(),
        )
