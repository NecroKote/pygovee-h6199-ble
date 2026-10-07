# Errors

[Getting started](index.md) · [Timeouts](timeouts.md) · [Device events](events.md)

Device-operation errors derive from `GoveeError`:

| Exception | Meaning |
|---|---|
| `UnsupportedFeature` | A capability or mode restriction prevents the operation. |
| `NotStarted` | Commands were called before start or after stop. |
| `CommandTimeout` | A write or response deadline expired; `error.phase` identifies which. |
| `TransportError` | A BLE operation failed. |
| `InvalidResponse` | A device reply could not be decoded. |

Wrapped errors retain their original exception as `__cause__`. Caller validation continues to raise `ValueError`; task cancellation continues to propagate `asyncio.CancelledError`. `CommandTimeout` also inherits `TimeoutError` for compatibility.

See [connection lifecycle](connection.md) for starting and stopping the client, and [device events](events.md#disconnects) for disconnect notifications.
