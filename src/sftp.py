"""Streaming SFTP destination with atomic remote publication."""

from dataclasses import dataclass, field
from logging import getLogger
from pathlib import PurePosixPath
from uuid import uuid4

from paramiko import SSHClient

from contracts import ChunkUploader
from journal import logged_suppress
from settings import SafeSettings

log = getLogger(__name__)


@dataclass
class SftpSettings(SafeSettings):
    required = {"SFTP_HOST", "SFTP_USER", "SFTP_KNOWN_HOSTS", "DESTINATION_PATH"}

    host: str
    user: str
    known_hosts: str
    destination: PurePosixPath
    password: str | None = field(default=None, repr=False)
    key_filename: str | None = None
    port: int = 22
    timeout: float = 30

    @classmethod
    def validate(cls, values):
        super().validate(values)
        if not (values.get("SFTP_PASSWORD") or values.get("SFTP_KEY_FILENAME")):
            raise ValueError("SftpSettings requires SFTP_PASSWORD or SFTP_KEY_FILENAME")

    @classmethod
    def from_values(cls, values):
        return cls(
            host=values["SFTP_HOST"],
            user=values["SFTP_USER"],
            known_hosts=values["SFTP_KNOWN_HOSTS"],
            destination=PurePosixPath(values["DESTINATION_PATH"]),
            password=values.get("SFTP_PASSWORD") or None,
            key_filename=values.get("SFTP_KEY_FILENAME") or None,
            port=int(values.get("SFTP_PORT", cls.port)),
            timeout=float(values.get("SFTP_TIMEOUT", cls.timeout)),
        )


class SftpUploader(ChunkUploader):
    """Publish only after all writes and the remote file close succeed."""

    UPLOAD_THRESHOLD = 64 * 1024

    def __init__(self, settings: SftpSettings):
        self.settings = settings
        path = settings.destination
        self.temporary_path = str(path.with_name(f".{path.name}.{uuid4().hex}.part"))
        self.client = SSHClient()
        self.sftp = None
        self.stream = None
        self.temporary_created = False

    def __enter__(self):
        try:
            self.client.load_host_keys(self.settings.known_hosts)
            self.client.connect(
                self.settings.host,
                port=self.settings.port,
                username=self.settings.user,
                password=self.settings.password,
                key_filename=self.settings.key_filename,
                allow_agent=False,
                look_for_keys=False,
                timeout=self.settings.timeout,
                banner_timeout=self.settings.timeout,
                auth_timeout=self.settings.timeout,
                channel_timeout=self.settings.timeout,
            )
            self.sftp = self.client.open_sftp()
            self.sftp.get_channel().settimeout(self.settings.timeout)
            self.stream = self.sftp.open(self.temporary_path, "wx", bufsize=0)
            self.temporary_created = True
            log.debug("Writing SFTP export to %s", self.temporary_path)
        except BaseException:
            self._cleanup()
            raise
        return self

    def send(self, chunk: memoryview) -> None:
        self.stream.write(bytes(chunk))

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.stream.close()
                self.stream = None
                self.sftp.posix_rename(self.temporary_path, str(self.settings.destination))
                self.temporary_created = False
                log.info("SFTP export saved to %s", self.settings.destination)
        finally:
            self._cleanup()
        return False

    def _cleanup(self):
        if self.stream is not None:
            with logged_suppress(log, "Failed to close SFTP export file"):
                self.stream.close()
            self.stream = None
        if self.temporary_created:
            with logged_suppress(log, "Failed to remove SFTP temporary file"):
                self.sftp.remove(self.temporary_path)
            self.temporary_created = False
        if self.sftp is not None:
            with logged_suppress(log, "Failed to close SFTP session"):
                self.sftp.close()
            self.sftp = None
        with logged_suppress(log, "Failed to close SSH connection"):
            self.client.close()
