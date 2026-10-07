# Connection

[Getting started](index.md) · [Device events](events.md) · [Timeouts](timeouts.md)

## Starting and stopping

The caller owns the Bleak connection. Use `async with GoveeH6199(client)` to start notifications and keep-alive, and stop them on exit. For manual lifecycle management, call `start()` and `stop()`. Device operations before `start()` or after `stop()` immediately raise `NotStarted`.

`connected(client, ...)` is an async context-manager shorthand for `GoveeH6199(client, ...)`. It forwards `logger`, `device_info`, `timeouts`, `keep_alive_interval` and `optional_response_timeout`; the caller still owns the Bleak connection.

## Keep-alive

The device drops a connection that has been idle for about 10 s, so while started the client sends a power read after `keep_alive_interval` (5 s by default, `None` disables) of silence.

Keep-alive timeouts are logged and retried; other failures are logged and stop keep-alive. See [device events](events.md#disconnects) for disconnect detection and recovery, and [timeouts](timeouts.md) for command deadlines.
