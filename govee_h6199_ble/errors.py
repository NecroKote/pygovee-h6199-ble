class GoveeError(Exception):
    """Base class of the library errors"""


class UnsupportedFeature(GoveeError):
    """The connected device can't do what was asked"""

    def __init__(self, feature: str, reason: str):
        super().__init__(f"{feature} is not supported: {reason}")
        self.feature = feature
        self.reason = reason
