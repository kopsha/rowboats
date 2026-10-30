"""Streaming FTP destination with temporary-file publication."""

from dataclasses import dataclass, field
from ftplib import FTP
from logging import getLogger
from pathlib import PurePosixPath
from uuid import uuid4

from contracts import ChunkUploader
from journal import logged_suppress
from settings import SafeSettings

log = getLogger(__name__)


@dataclass
class FtpSettings(SafeSettings):
    required = {
        "FTP_HOST",
        "FTP_USER",
        "FTP_PASSWORD",
        "DESTINATION_PATH",
    }

    host: str
    user: str
    password: str = field(repr=False)
    destination: PurePosixPath
    port: int = 21
    timeout: float = 30

    @classmethod
    def from_values(cls, values):
        return cls(
            values["FTP_HOST"],
            values["FTP_USER"],
            values["FTP_PASSWORD"],
            PurePosixPath(values["DESTINATION_PATH"]),
            int(values.get("FTP_PORT", cls.port)),
            float(values.get("FTP_TIMEOUT", cls.timeout)),
        )


class FtpUploader(ChunkUploader):
    """Stream one binary upload and publish it only after successful exit."""

    UPLOAD_THRESHOLD = 64 * 1024

    def __init__(self, settings: FtpSettings):
        self.settings = settings
        path = settings.destination
        self.temporary_path = str(path.with_name(f".{path.name}.{uuid4().hex}.part"))
        self.client = FTP()
        self.data = None

    def __enter__(self):
        try:
            self.client.connect(
                self.settings.host, self.settings.port, timeout=self.settings.timeout
            )
            self.client.login(self.settings.user, self.settings.password)
            self.client.voidcmd("TYPE I")
            self.data = self.client.transfercmd(f"STOR {self.temporary_path}")
        except BaseException:
            self._close_client()
            raise
        return self

    def send(self, chunk: memoryview) -> None:
        self.data.sendall(chunk)

    def __exit__(self, exc_type, exc_value, traceback):
        self._close_data()
        if exc_type is None:
            self._publish()
        self._close_client()
        return False

    def _publish(self):
        with logged_suppress(log, "Failed to publish FTP upload"):
            self.client.voidresp()
            self.client.rename(self.temporary_path, str(self.settings.destination))

    def _close_data(self):
        with logged_suppress(log, "Failed to close FTP data connection"):
            if self.data is not None:
                self.data.close()
                self.data = None

    def _close_client(self):
        with logged_suppress(log, "Failed to close FTP control connection"):
            self.client.close()
