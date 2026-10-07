# Hardware coverage and low-level access

[Getting started](index.md) · [API reference](api.md) · [Connection](connection.md) · [Errors](errors.md)

## Hardware coverage

The client was tested on one device with these versions:

| Component | Firmware version | Hardware version |
|---|---|---|
| Light controller | 1.10.04 | 3.02.01 |
| Wi-Fi chip | 1.00.33 | 1.03.00 |

Capability rules cover additional versions, but those combinations have not been verified on hardware here.

## Limitations

Music sensitivity, fixed color and the calm flag cannot be read back. Scenes and DIY are not supported.

## Low-level access

`light.transport` sends raw commands from `govee_h6199_ble.protocol.commands` or raw frames:

```python
from govee_h6199_ble import CommandTimeouts
from govee_h6199_ble.protocol.commands import GetPact

pact = await light.transport.send_command(GetPact())
raw = await light.transport.exchange_frame(frame, CommandTimeouts())
```

Raw commands use the same error model as high-level calls. Invalid received frame lengths or checksums raise `InvalidResponse`.

`light.transport.last_activity` is the `time.monotonic()` of the last frame *sent*; keep-alive uses it. `light.transport.last_received` is the `time.monotonic()` of the last frame received, or `None`. Prefer `light.last_seen` for liveness.
