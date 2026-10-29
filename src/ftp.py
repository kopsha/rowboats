"""Streaming FTP destination with temporary-file publication."""

from contextlib import suppress
from dataclasses import dataclass, field
from ftplib import FTP
from pathlib import PurePosixPath
from uuid import uuid4

from contracts import ChunkUploader
from settings import SafeSettings


@dataclass
class FtpSettings(SafeSettings):
    required = {"FTP_HOST", "FTP_USER", "FTP_PASSWORD", "DESTINATION_PATH"}

    host: str
    user: str
    password: str = field(repr=False)
    destination_path: str
    port: int = 21
    timeout: float = 30

    @classmethod
    def from_values(cls, values):
        port = int(values.get("FTP_PORT", "21"))
        timeout = float(values.get("FTP_TIMEOUT", "30"))
        if not 1 <= port <= 65535:
            raise ValueError("FTP_PORT must be between 1 and 65535")
        if not 0 < timeout < float("inf"):
            raise ValueError("FTP_TIMEOUT must be positive and finite")
        path = values["DESTINATION_PATH"]
        if not PurePosixPath(path).name or path.endswith("/"):
            raise ValueError("DESTINATION_PATH must name a remote file")
        if any(
            c in value
            for value in (path, values["FTP_USER"], values["FTP_PASSWORD"])
            for c in "\r\n"
        ):
            raise ValueError("FTP settings must not contain newlines")
        return cls(
            values["FTP_HOST"], values["FTP_USER"], values["FTP_PASSWORD"], path, port, timeout
        )


class FtpUploader(ChunkUploader):
    """Send one binary transfer, then rename it to the destination on success."""

    UPLOAD_THRESHOLD = 64 * 1024

    def __init__(self, settings: FtpSettings):
        self.settings = settings

    def _connect(self):
        client = FTP()
        try:
            client.connect(self.settings.host, self.settings.port, timeout=self.settings.timeout)
            client.login(self.settings.user, self.settings.password)
        except BaseException:
            client.close()
            raise
        return client

    def __enter__(self):
        path = PurePosixPath(self.settings.destination_path)
        self.temporary_path = str(path.with_name(f".{path.name}.{uuid4().hex}.part"))
        self.client = self._connect()
        self.data = None
        self.started = False
        try:
            self.client.voidcmd("TYPE I")
            self.started = True
            self.data = self.client.transfercmd(f"STOR {self.temporary_path}")
        except BaseException:
            self._discard()
            raise
        return self

    def send(self, chunk):
        self.data.sendall(chunk)

    def _discard(self):
        # A failed transfer can leave unread replies on the control connection.
        # Use a fresh session for cleanup so replies cannot get out of sync.
        if self.data is not None:
            with suppress(Exception):
                self.data.close()
        self.client.close()
        if self.started:
            with suppress(Exception):
                cleanup = self._connect()
                try:
                    cleanup.delete(self.temporary_path)
                finally:
                    cleanup.close()

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self._discard()
            return False
        try:
            self.data.close()
            self.client.voidresp()
            self.client.rename(self.temporary_path, self.settings.destination_path)
        except BaseException:
            self._discard()
            raise
        finally:
            self.client.close()
        return False
