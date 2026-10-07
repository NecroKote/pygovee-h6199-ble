class GoveeError(Exception):
    """Base class of the library errors"""


class UnsupportedFeature(GoveeError):
    """The connected device can't do what was asked"""

    def __init__(self, feature: str, reason: str):
        super().__init__(f"{feature} is not supported: {reason}")
        self.feature = feature
        self.reason = reason


class CommandTimeout(GoveeError, TimeoutError):
    """A command deadline expired; `phase` identifies the operation."""

    def __init__(self, message: str = "command timed out", phase: str = "response"):
        super().__init__(message)
        self.phase = phase


class NotStarted(GoveeError):
    """Start notifications before sending commands."""


class TransportError(GoveeError):
    """A BLE operation failed; the original exception is in `__cause__`."""


class InvalidResponse(GoveeError):
    """A device response could not be decoded."""
