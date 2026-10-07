# Upgrading

[Getting started](index.md) · [API reference](api.md)

## Upgrading from 1.x to 2.x

Command classes are no longer exported from the package root. Prefer `GoveeH6199` methods for normal device operations.

Before, in 1.x:

```python
from govee_h6199_ble import GetPowerState, PowerOn

# Inside a started GoveeH6199 session:
await light.send_command(PowerOn())
on = await light.send_command(GetPowerState())
```

After, in 2.x:

```python
# Inside a started GoveeH6199 session:
await light.set_power(True)
on = await light.get_power()
```

### Raw commands and frames

If you need command classes, import them from `govee_h6199_ble.protocol.commands`. Raw `send_command`, `send_commands` and `exchange_frame` calls moved to `light.transport`:

```python
from govee_h6199_ble.protocol.commands import GetPowerState

on = await light.transport.send_command(GetPowerState())
```

Import `CommandTimeouts` from `govee_h6199_ble`. Use `CommandTimeouts(write=None, response=None)` to disable both deadlines explicitly; raw `send_command(..., timeouts=None)` uses the default deadlines and returns `None` on timeout. See [timeouts](timeouts.md).

### Input and frame changes

- Music sensitivity must be an integer from 0–99.
- Video-mode commands always include the sound-effect fields. Use `set_video_mode()` to construct the appropriate command.
- Device operations before `start()` or after `stop()` raise `NotStarted`. Use `async with GoveeH6199(client)` or manage `start()` and `stop()` explicitly; see [connection](connection.md).
- Device-operation failures derive from `GoveeError`; invalid inputs raise `ValueError`. See [errors](errors.md) for exception handling.
