# Timeouts

[Getting started](index.md) · [Errors](errors.md) · [Connection](connection.md)

## Defaults

The default `CommandTimeouts(write=None, response=5.0)` allows the write to wait indefinitely and gives each response five seconds after the write completes. These deadlines apply to **setters too**, although they return `None`: a device that does not acknowledge a setter raises `CommandTimeout`. Neither deadline limits time waiting for another command to release the transport lock.

## Configuration

Pass a `CommandTimeouts` object to the `GoveeH6199` constructor to configure device operations:

```python
from govee_h6199_ble import CommandTimeouts, GoveeH6199

light = GoveeH6199(client, timeouts=CommandTimeouts(write=3.0, response=5.0))
```

A `None` field disables that deadline. For example, `CommandTimeouts(write=None, response=None)` disables both deadlines.

### Raw transport calls

For `light.transport.send_command`, passing `timeouts=None` has a separate meaning: use the default deadlines and return `None` on timeout. BLE and parsing failures still raise exceptions.

| Raw transport configuration | Deadlines | On timeout |
|---|---|---|
| Omit `timeouts` | Write: unlimited; response: 5 seconds | Raise `CommandTimeout` |
| `timeouts=CommandTimeouts(write=3.0, response=5.0)` | Write: 3 seconds; response: 5 seconds | Raise `CommandTimeout` |
| `timeouts=CommandTimeouts(write=None, response=None)` | Both unlimited | No command deadline expires |
| `timeouts=None` | Write: unlimited; response: 5 seconds | Return `None` |

For batches, `transport.send_commands(..., command_timeouts=None)` uses the same deadlines and includes `None` in the returned list for each command that times out. Use `CommandTimeouts` to configure the `GoveeH6199` client or `transport.exchange_frame`.

## Optional device information

When discovering device information, the Wi-Fi firmware version, Wi-Fi hardware version and protocol identifier (`Pact`) are optional reads. Each uses `optional_response_timeout=2.0` on the `GoveeH6199` client and the configured write deadline. Set `optional_response_timeout=None` to wait indefinitely for these responses.

Only a response timeout leaves the corresponding field (`wifi_soft`, `wifi_hard` or `pact`) as `None`, with a warning. Write timeouts, malformed replies and BLE errors propagate.
