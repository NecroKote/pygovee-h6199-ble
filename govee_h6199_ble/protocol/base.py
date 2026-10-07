from abc import ABC, abstractmethod
from typing import Generic, NamedTuple, TypeVar

from .const import PacketHeader, PacketType

T = TypeVar("T")


class CommandPayload(NamedTuple):
    header: PacketHeader
    domain: PacketType | int
    payload: list[int]


class Command(ABC):
    @abstractmethod
    def payload(self) -> CommandPayload: ...


class CommandWithParser(Command, ABC, Generic[T]):
    @abstractmethod
    def parse_response(self, response: bytes) -> T: ...
