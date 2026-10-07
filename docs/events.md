# Device events

[Getting started](index.md) · [Connection](connection.md) · [Errors](errors.md)

The device sends notifications for some changes, including power, brightness and Wi-Fi connection state. Register a listener to receive typed events:

```python
remove_listener = light.add_listener(print)
# Later, stop receiving events:
remove_listener()
```

Listeners are synchronous callbacks that run in the event loop and must not block. Listener removal is idempotent: calling the removal function again is harmless.

## Event types

| Event | Fields | Meaning |
|---|---|---|
| `PowerChanged` | `on: bool` | Whether the light is on. |
| `BrightnessChanged` | `brightness: int` | Overall brightness. Protocol generation V1 notifications use a 1–254 scale; the library converts them to a percentage once V1 capabilities are known. |
| `WifiStateChanged` | `connected: bool` | Whether the device’s Wi-Fi connection is active. |
| `MovieModeChanged` | `on: bool` | The device’s movie-mode notification flag. This event does not provide a complete video-mode state; use `get_video_mode()` to read video parameters. |
| `SubDeviceStatus` | `slots: bytes` | Status bytes for sub-device slots; not meaningful for a single light. |
| `UnknownNotification` | `id: int`, `payload: bytes` | A notification the library does not recognize or cannot decode. |
| `Disconnected` | `reason: str` | A BLE failure detected by the library, rather than a device notification. |

## Disconnects

A detected BLE failure emits `Disconnected(reason)` once per started session and stops transport command access. A command that detects the failure raises `TransportError`; a keep-alive failure is logged. Detection happens during a command or keep-alive; it is not an immediate Bleak disconnect callback. With keep-alive disabled, an idle disconnect is discovered by the next command.

The library does not reconnect automatically. Stop the `GoveeH6199` client, reconnect the caller-owned Bleak client, then start notifications and keep-alive again. For manual lifecycle management, the recovery sequence is:

```python
# Run this in an async function after detecting a disconnect.
await light.stop()
if client.is_connected:
    await client.disconnect()
await client.connect()
await light.start()
```

Existing listeners remain registered. When using context managers, exit the old contexts and enter new ones to establish another session.

See [connection and keep-alive](connection.md#keep-alive) for idle connection handling.
