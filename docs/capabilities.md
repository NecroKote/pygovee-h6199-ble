# Capabilities

[Getting started](index.md) · [API reference](api.md) · [Errors](errors.md)

Feature availability depends on hardware versions, firmware versions and protocol generation. `get_capabilities()` returns a cached `Capabilities` object. The flags below identify which high-level operations the library enables.

Other fields describe device features or command selection: `chip` identifies the controller hardware family, and `legacy_color` selects commands for protocol generation V1. `service_scenes`, `ai_effects` and `phone_mic_music` describe device features; they do not provide corresponding high-level library operations. Scenes and DIY remain unsupported.

## Device terminology

- **Protocol identifier (`Pact`):** the `(type, code)` pair reported by the device. Its `generation` is a known protocol generation V1–V4, or `None` for an unknown pair. A missing identifier is represented as `None` in `DeviceInfo.pact`.
- **Telink:** the controller hardware family used by hardware version 1.x. Its video-brightness commands require video mode to be active.
- **Screen-edge brightness:** relative brightness for the left, top, right and bottom screen edges. The corresponding capability flag is named `video_segment_brightness`. These four edges are distinct from the 15 numbered color zones.

## Supported actions

The methods listed below require these capability flags:

| Capability | Actions |
|---|---|
| No capability flag required | power, overall brightness, static color, color temperature, zone colors, gradient, music modes, video mode, reads of the mode and zones |
| `zone_brightness` | `set_zone_brightness`, `set_zone_brightnesses` |
| `video_brightness` / `video_segment_brightness` | `set_video_brightness`, `get_video_brightness` |
| `video_segment_brightness` | `set_video_edge_brightness`, `get_video_edge_brightness` |
| `white_balance` | `set_white_balance`, `set_white_balance_raw`, `set_white_balance_auto`, `reset_white_balance`, `get_white_balance` |
| `black_screen` | `get_black_screen`, `set_black_screen`, `update_black_screen` |

## Capability checks

Calling a gated method on a device without the capability raises `UnsupportedFeature`. Every gated getter, setter and update takes `force=True` to bypass the capability check. This does not bypass value validation or Telink's requirement that video mode be active. `set_video_mode(brightness=...)` also checks brightness support before writing; it accepts `force` too. A missing or unknown protocol identifier does not enable zone brightness. Firmware-based capabilities still use known version information.

## Reading and refreshing

`get_capabilities()` reads device information on first use and caches the result. Pass `refresh=True` to reread that information and recalculate capabilities.

```python
caps = await light.get_capabilities()
if caps.white_balance:
    await light.set_white_balance(10)
```
