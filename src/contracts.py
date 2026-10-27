from abc import abstractmethod
from contextlib import AbstractContextManager
from typing import ClassVar, Iterable, Iterator


class TableSource(AbstractContextManager):
    """Yield rows with a stable, ordered schema within a context.

    Entry prepares the source; exit closes resources and preserves exceptions.
    Implementations must also clean up resources when entry fails.
    """

    @abstractmethod
    def columns(self) -> Iterable[str]:
        """Return column names in export order, available after context entry."""
        pass

    @abstractmethod
    def rows(self) -> Iterator:
        """Yield rows for the active query."""
        pass


class ChunkUploader(AbstractContextManager):
    """Upload chunks synchronously in order within a context.

    Entry prepares the upload; exit commits on success or cancels on failure.
    Implementations preserve exceptions and clean up failed entry or commit.
    """

    # Minimum size for non-final chunks; the last chunk may be smaller.
    UPLOAD_THRESHOLD: ClassVar[int]

    @abstractmethod
    def send(self, chunk: memoryview) -> None:
        """Consume a chunk synchronously in call order, or raise on failure."""
        pass
