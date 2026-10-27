"""Local CSV source and file destination using only the standard library."""

import csv
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from contracts import ChunkUploader, TableSource
from settings import SafeSettings


@dataclass
class LocalSettings(SafeSettings):
    required = {"SOURCE_PATH", "DESTINATION_PATH"}

    source_path: Path
    destination_path: Path

    @classmethod
    def from_values(cls, values):
        return cls(Path(values["SOURCE_PATH"]), Path(values["DESTINATION_PATH"]))


class CsvSource(TableSource):
    def __init__(self, settings: LocalSettings) -> None:
        super().__init__()
        self.settings = settings

    def __enter__(self):
        self.stream = self.settings.source_path.open(encoding="utf-8", newline="")
        try:
            self.reader = csv.reader(self.stream)
            self.header = next(self.reader)
        except BaseException:
            self.stream.close()
            raise
        return self

    def columns(self):
        return self.header

    def rows(self):
        return self.reader

    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.close()
        return False


class FileUploader(ChunkUploader):
    """Replace the destination only after the entire export succeeds."""

    UPLOAD_THRESHOLD = 64 * 1024

    def __init__(self, settings: LocalSettings) -> None:
        super().__init__()
        self.settings = settings

    def __enter__(self):
        self.stream = NamedTemporaryFile(
            mode="wb", dir=self.settings.destination_path.parent, delete=False
        )
        self.temporary_path = Path(self.stream.name)
        return self

    def send(self, chunk):
        self.stream.write(chunk)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stream.close()
            if exc_type is None:
                self.temporary_path.replace(self.settings.destination_path)
        finally:
            self.temporary_path.unlink(missing_ok=True)
        return False
