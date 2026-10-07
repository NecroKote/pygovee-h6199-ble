# API reference

This page documents `GoveeH6199`. Methods are asynchronous and must be awaited, except for the constructor and `add_listener`; `transport` is a property.

## Common conventions

- Start the `GoveeH6199` client with `async with` or `start()` before device operations. See [connection](connection.md).
- Invalid inputs raise `ValueError`. Device-operation failures derive from `GoveeError`; see [errors](errors.md) and [timeouts](timeouts.md).
- Setters wait for a device reply and return `None`, except `set_color_temperature`, which returns the rounded kelvin value.
- Zones are numbered 0–14. `zones=None` selects all zones; empty selections and invalid indices raise `ValueError`.
- Mode and state dataclasses are frozen, and zone collections are tuples. Use `dataclasses.replace()` to create modified snapshots.
- `force=True` bypasses capability checks, but not input validation or active-mode requirements. See [capabilities](capabilities.md).
- White balance, black-screen settings and video writes are serialized within one `GoveeH6199` client, including read-modify-write helpers. Raw transport calls, other clients and remotes can still race them.

## Creating a client

### GoveeH6199

```python
light = GoveeH6199(
    client,
    logger=None,
    device_info=None,
    timeouts=CommandTimeouts(),
    keep_alive_interval=5.0,
    optional_response_timeout=2.0,
)
```

| Parameter | Purpose |
|---|---|
| `client` | An already connected `BleakClient`, owned by the caller. |
| `logger` | Optional logger; otherwise use the library’s default logger. |
| `device_info` | Optional known `DeviceInfo`, avoiding initial version reads. |
| `timeouts` | Write and response deadlines; see [timeouts](timeouts.md). |
| `keep_alive_interval` | Seconds of silence before a power read; `None` disables keep-alive. |
| `optional_response_timeout` | Response deadline for optional Wi-Fi version and protocol-identifier reads; `None` waits indefinitely. |

### transport

**Type:** `Transport`

Access the underlying transport to send raw commands and frames. See [low-level access](advanced.md#low-level-access).

## Lifecycle and events

### start

**Signature:** `start() → None`

Start notifications and the keep-alive task. The underlying Bleak client must already be connected. Calling this on an already started `GoveeH6199` client is harmless.

See [connection](connection.md) for manual lifecycle management or use `async with`.

### stop

**Signature:** `stop() → None`

Stop keep-alive and notifications. This does not disconnect the caller-owned Bleak client. Calling this on an already stopped `GoveeH6199` client is harmless.

### add_listener

**Signature:** `add_listener(listener) → Callable[[], None]`

Register a synchronous callback receiving a `DeviceEvent`. It runs in the event loop and must not block. Returns an idempotent function that removes the listener.

See [device events](events.md) for event types and disconnect notifications.

## Device information and capabilities

### get_device_info

**Signature:** `get_device_info(refresh=False) → DeviceInfo`

Read and cache device information. `soft` and `hard` are the light controller’s firmware and hardware versions; `wifi_soft` and `wifi_hard` are the Wi-Fi chip’s firmware and hardware versions. Each version is a `Version` object. The Wi-Fi versions and protocol identifier (`pact`) are optional and may be `None`. See [device terminology](capabilities.md#device-terminology).

Pass `refresh=True` to reread all inputs and invalidate cached capabilities. Optional reads use the [optional information timeout](timeouts.md#optional-device-information); malformed replies and BLE errors propagate.

### get_capabilities

**Signature:** `get_capabilities(refresh=False) → Capabilities`

Return cached feature flags, reading device information on first use. `refresh=True` rereads all inputs and recalculates the flags.

See [capabilities](capabilities.md) for the feature table and override rules.

### get_firmware_version

**Signature:** `get_firmware_version() → Version`

Read the device firmware version on every call. Use `str(version)` for its dotted representation.

### get_hardware_version

**Signature:** `get_hardware_version() → Version`

Read the device hardware version on every call. Use `str(version)` for its dotted representation.

### get_mac_address

**Signature:** `get_mac_address() → str`

Read the Wi-Fi chip MAC address, formatted as colon-separated hexadecimal bytes.

### get_pact

**Signature:** `get_pact() → Pact`

Read the protocol identifier on every call. `Pact` contains the `(type, code)` pair reported in advertisements and by the device. `Pact.generation` identifies known generations V1–V4, or returns `None` for an unknown pair.

## Power and overall brightness

### get_power

**Signature:** `get_power() → bool`

Read whether the light is on.

### set_power

**Signature:** `set_power(on) → None`

Turn the light on with `True`, or off with `False`.

### get_brightness

**Signature:** `get_brightness() → int`

Read overall brightness as a percentage. Protocol generation V1 readings are converted from the device’s 1–254 scale.

### set_brightness

**Signature:** `set_brightness(percent) → None`

Set overall brightness to an integer from 1–100. Protocol generation V1 writes are scaled and rounded to the device’s 1–254 range.

## Static colors and zones

### set_static_color

**Signature:** `set_static_color(color, zones=None) → None`

Switch to static color mode and apply one RGB color to the selected zones. `color` is a three-item sequence, such as a tuple or list, with components from 0–255. `zones=None` selects all zones.

### set_color_temperature

**Signature:** `set_color_temperature(kelvin, zones=None) → int`

Switch to static color mode with a temperature from 2000–9000 K. Return the actual kelvin value sent.

Inputs within that range are rounded to the nearest table value; halfway values round down. The table has 100 K steps through 6500 K, then 7000, 7200, 8000, 8200 and 9000 K. Out-of-range inputs raise `ValueError`; they are not clamped. `zones=None` selects all zones.

### set_zone_colors

**Signature:** `set_zone_colors(colors) → None`

Switch to static color mode and paint zones using either a mapping `{zone: color}` or a sequence of exactly 15 RGB colors. Each color has three components from 0–255.

Unspecified zones in a mapping keep their color. Zones sharing a color are written in one frame.

### set_zone_brightness

**Signature:** `set_zone_brightness(percent, zones=None, force=False) → None`

Set one integer percentage, 1–100, for selected zones; `zones=None` selects all zones.

Requires `caps.zone_brightness`, unless `force=True`.

### set_zone_brightnesses

**Signature:** `set_zone_brightnesses(percents, force=False) → None`

Set individual zone brightness using a sequence of exactly 15 integers from 1–100, in zone order. This method does not accept a mapping.

Requires `caps.zone_brightness`, unless `force=True`.

### get_zone_states

**Signature:** `get_zone_states() → tuple[ZoneState, ...]`

Read all 15 zones in four requests. Each `ZoneState` contains `brightness` and an RGB `color`; its `kelvin` property returns a matching color-table temperature, or `None`.

### get_gradient

**Signature:** `get_gradient() → bool`

Read whether the smooth color gradient between zones is enabled.

### set_gradient

**Signature:** `set_gradient(enabled) → None`

Enable or disable the smooth color gradient between zones.

## Current mode and state

### get_mode

**Signature:** `get_mode(include_zones=False) → Modes`

Read one of `StaticColorMode`, `MusicColorMode`, `VideoColorMode` or `UnknownColorMode`.

The default sends one mode request. With `include_zones=True`, static mode adds four zone requests and any device-information discovery needed to choose the zone commands. `StaticColorMode.zones` is otherwise `None`. Its `kind` identifies the last static frame when reported; it is `None` on the tested firmware.

Known modes expose a `mode` discriminator. `UnknownColorMode.raw_mode` contains the raw protocol byte.

### read_state

**Signature:** `read_state() → DeviceState`

Read power, overall brightness, mode and all 15 zones sequentially. The result is not an atomic device snapshot. Its `mode` is read without embedded zones; use `state.zones` for the zone tuple.

## Music mode

### get_music_mode

**Signature:** `get_music_mode() → MusicColorMode | None`

Read the current music effect, or return `None` if music mode is inactive. Sensitivity, fixed color and the calm flag cannot be read back.

### set_music_mode

**Signature:** `set_music_mode(effect, sensitivity=99, color=None, calm=True) → None`

Switch to a `MusicMode` effect: `RHYTHM`, `SPECTRUM`, `ENERGIC` or `ROLLING`. Sensitivity is an integer from 0–99.

`color=None` uses automatic colors; otherwise supply three RGB components from 0–255. Energic ignores `color`. `calm` applies only to rhythm. The deprecated spelling `RYTHM` remains an alias for `RHYTHM`.

## Video mode and brightness

### get_video_mode

**Signature:** `get_video_mode() → VideoColorMode | None`

Read video parameters, or return `None` if video mode is inactive. Zero saturation, softness or brightness in a reply is represented as `None`, meaning unspecified.

`VideoColorMode` construction defaults for saturation and softness are 50; brightness defaults to `None`.

### set_video_mode

**Signature:** `set_video_mode(full_screen=True, game_mode=False, saturation=50, sound_effects=False, sound_effects_softness=50, brightness=None, force=False) → None`

Switch to video mode (camera-driven lighting). `full_screen` selects full-screen sampling and `game_mode` selects game mode. `saturation` and `sound_effects_softness` are integers from 1–100. `sound_effects` enables sound effects.

Optional `brightness` is 1–100; `None` leaves it unchanged. Supplying brightness requires `caps.video_brightness` or `caps.video_segment_brightness`, unless `force=True`. This check happens before writing. Brightness is applied using the firmware-specific behavior of [set_video_brightness](#set_video_brightness).

### get_video_brightness

**Signature:** `get_video_brightness(force=False) → int | EdgeBrightness`

Requires `caps.video_brightness` or `caps.video_segment_brightness`, unless `force=True`. The return value depends on firmware:

| Firmware behavior | Return value |
|---|---|
| Screen-edge brightness | `EdgeBrightness(left, top, right, bottom)` |
| Telink (hardware version 1.x) | Integer brightness from the active video frame |
| Whole-screen brightness | One integer percentage |

Telink requires active video mode, otherwise raises `UnsupportedFeature`. A Telink reply without brightness raises `InvalidResponse`.

### set_video_brightness

**Signature:** `set_video_brightness(percent, force=False) → None`

Set video brightness to an integer from 1–100. Requires `caps.video_brightness` or `caps.video_segment_brightness`, unless `force=True`.

Firmware with screen-edge brightness support writes the same value to all four edges. Telink reads and rewrites the active video frame, using 50 for unspecified saturation or softness; inactive video mode raises `UnsupportedFeature`. Other firmware uses the whole-screen command. `force` does not bypass the Telink active-mode requirement.

### get_video_edge_brightness

**Signature:** `get_video_edge_brightness(force=False) → EdgeBrightness`

Read the relative brightness of the left, top, right and bottom screen edges. These four edges are distinct from the 15 color zones.

Requires `caps.video_segment_brightness`, unless `force=True`.

### set_video_edge_brightness

**Signature:** `set_video_edge_brightness(*, left, top, right, bottom, force=False) → None`

Set each edge’s relative brightness to an integer from 1–100. All edge values are keyword-only.

Requires `caps.video_segment_brightness`, unless `force=True`.

## White balance

### get_white_balance

**Signature:** `get_white_balance(force=False) → WhiteBalanceState`

Read `current`, a `WhiteBalance(auto, red, blue)`, and `default`, the device’s default `(red, blue)` pair. `current.step` returns the corresponding slider step, or `None` for a pair outside the defined table.

Requires `caps.white_balance`, unless `force=True`.

### set_white_balance

**Signature:** `set_white_balance(step, force=False) → None`

Apply manual white balance using a defined slider step from 1–20.

Requires `caps.white_balance`, unless `force=True`.

### set_white_balance_raw

**Signature:** `set_white_balance_raw(white_balance, force=False) → None`

Write a `WhiteBalance` with explicit `auto`, `red` and `blue` values. Red and blue must each be 1–31; they are used when automatic balance is off. Prefer [set_white_balance](#set_white_balance) for the defined slider steps.

Requires `caps.white_balance`, unless `force=True`.

### set_white_balance_auto

**Signature:** `set_white_balance_auto(force=False) → None`

Enable automatic white balance, reading and preserving the stored manual red/blue pair.

Requires `caps.white_balance`, unless `force=True`.

### reset_white_balance

**Signature:** `reset_white_balance(force=False, *, auto=None) → None`

Read and restore the device’s default red/blue pair. `auto=None` preserves the current automatic flag; pass `auto=True` or `False` to choose it explicitly.

Requires `caps.white_balance`, unless `force=True`.

## Black-screen settings

### get_black_screen

**Signature:** `get_black_screen(force=False) → BlackScreenSetting`

Read what the lights do when the picture goes black in video mode: `enabled`, `mode`, `low_brightness_seconds` and `same_tone_seconds`.

Requires `caps.black_screen`, unless `force=True`.

### set_black_screen

**Signature:** `set_black_screen(setting, force=False) → None`

Write a complete `BlackScreenSetting`. Its mode is `BlackScreenMode.LOW_BRIGHTNESS` or `SAME_TONE`. Low-brightness delay must be 5–300 seconds; same-tone delay must be 120–1800 seconds. Both durations are always sent.

Invalid durations raise `ValueError`. Call `setting.normalized()` explicitly to replace invalid durations with defaults of 10 and 300 seconds.

Requires `caps.black_screen`, unless `force=True`.

### update_black_screen

**Signature:** `update_black_screen(enabled=None, mode=None, low_brightness_seconds=None, same_tone_seconds=None, force=False) → None`

Read the current setting, replace fields supplied with non-`None` values, then write it back. Unspecified fields are preserved.

The resulting durations must satisfy the same ranges as [set_black_screen](#set_black_screen). Invalid stored durations are not normalized silently; supply valid replacements if needed.

Requires `caps.black_screen`, unless `force=True`.
