from abc import ABC, abstractmethod
from os import environ
from typing import ClassVar, Mapping, Self


class SafeSettings(ABC):
    """Base settings with required environment keys."""

    required: ClassVar[set[str]] = set()

    @classmethod
    def validate(cls, values: Mapping[str, str]) -> None:
        """Reject missing or empty required values; report keys in sorted order."""
        missing = {key for key in cls.required if not values.get(key)}
        if missing:
            raise ValueError(
                "{name} is misconfigured. Missing: {keys}".format(
                    name=cls.__name__, keys=", ".join(sorted(missing))
                )
            )

    @classmethod
    def from_environment(cls) -> Self:
        """Validate environment variables and build settings from them."""
        values = dict(environ)
        cls.validate(values)
        return cls.from_values(values)

    @classmethod
    @abstractmethod
    def from_values(cls, values: Mapping[str, str]) -> Self:
        """Build settings from previously validated values."""
        pass


class UseSettings:
    """Mixin that stores settings during client construction."""

    def __init__(self, settings: SafeSettings, *args, **kwargs):
        self.settings = settings
        super().__init__(*args, **kwargs)
