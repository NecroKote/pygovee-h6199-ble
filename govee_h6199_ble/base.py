from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")
CommandPayload = tuple[int, int, bytes]


class Command(ABC):

    @abstractmethod
    def payload(self) -> CommandPayload: ...


class CommandWithParser(Generic[T], Command, ABC):

    @abstractmethod
    def parse_response(self, response: bytes) -> T: ...
