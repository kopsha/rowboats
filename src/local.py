"""Local settings and file destination using only the standard library."""

from dataclasses import dataclass
from logging import getLogger
from pathlib import Path
from tempfile import NamedTemporaryFile

from contracts import ChunkUploader
from settings import SafeSettings

log = getLogger(__name__)


@dataclass
class LocalSettings(SafeSettings):
    required = {"SOURCE_PATH", "DESTINATION_PATH"}

    source_path: Path
    destination_path: Path

    @classmethod
    def from_values(cls, values):
        return cls(Path(values["SOURCE_PATH"]), Path(values["DESTINATION_PATH"]))


class LocalFileSink(ChunkUploader):
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
        log.debug("Writing export to temporary file %s", self.temporary_path)
        return self

    def send(self, chunk):
        self.stream.write(chunk)

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stream.close()
            if exc_type is None:
                self.temporary_path.replace(self.settings.destination_path)
                log.info("Export saved to %s", self.settings.destination_path)
            else:
                log.warning(
                    "Export failed; discarding temporary file %s",
                    self.temporary_path,
                    exc_info=(exc_type, exc_value, traceback),
                )
        except Exception:
            log.exception("Failed to save export to %s", self.settings.destination_path)
            raise
        finally:
            try:
                self.temporary_path.unlink(missing_ok=True)
            except Exception:
                log.exception("Failed to remove temporary file %s", self.temporary_path)
                raise
        return False
