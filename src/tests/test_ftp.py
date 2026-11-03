from pathlib import PurePosixPath
from unittest.mock import Mock, call

import pytest

from ftp import FtpSettings, FtpUploader
from main import main


@pytest.fixture
def ftp(monkeypatch):
    client = Mock()
    monkeypatch.setattr("ftp.FTP", Mock(return_value=client))
    return client


def settings():
    return FtpSettings("localhost", "exporter", "secret", PurePosixPath("/exports/report.csv"))


def test_streams_binary_chunks_then_publishes(ftp):
    with FtpUploader(settings()) as uploader:
        uploader.send(memoryview(b"first"))
        uploader.send(memoryview(b"second"))
        ftp.rename.assert_not_called()

    assert ftp.mock_calls == [
        call.connect("localhost", 21, timeout=30),
        call.login("exporter", "secret"),
        call.voidcmd("TYPE I"),
        call.transfercmd(f"STOR {uploader.temporary_path}"),
        call.transfercmd().sendall(b"first"),
        call.transfercmd().sendall(b"second"),
        call.transfercmd().close(),
        call.voidresp(),
        call.rename(uploader.temporary_path, "/exports/report.csv"),
        call.close(),
    ]


@pytest.mark.parametrize("operation", ["connect", "login", "transfercmd"])
def test_failed_entry_closes_client(ftp, operation):
    getattr(ftp, operation).side_effect = OSError("setup failed")
    with pytest.raises(OSError, match="setup failed"):
        with FtpUploader(settings()):
            pytest.fail("entry should fail")
    ftp.close.assert_called_once()
    ftp.rename.assert_not_called()


def test_source_failure_closes_connections_without_publishing(ftp):
    with pytest.raises(RuntimeError, match="source failed"):
        with FtpUploader(settings()):
            raise RuntimeError("source failed")
    ftp.transfercmd.return_value.close.assert_called_once()
    ftp.close.assert_called_once()
    ftp.rename.assert_not_called()


def test_send_failure_closes_connections_without_publishing(ftp):
    ftp.transfercmd.return_value.sendall.side_effect = OSError("send failed")
    with pytest.raises(OSError, match="send failed"):
        with FtpUploader(settings()) as uploader:
            uploader.send(memoryview(b"partial"))
    ftp.transfercmd.return_value.close.assert_called_once()
    ftp.close.assert_called_once()
    ftp.rename.assert_not_called()


@pytest.mark.parametrize("operation", ["voidresp", "rename"])
def test_publication_failure_propagates_and_connections_are_closed(ftp, operation):
    error = OSError("publication failed")
    getattr(ftp, operation).side_effect = error
    with pytest.raises(OSError) as raised:
        with FtpUploader(settings()) as uploader:
            uploader.send(memoryview(b"content"))
    ftp.transfercmd.return_value.close.assert_called_once()
    ftp.close.assert_called_once()
    assert raised.value is error


@pytest.mark.parametrize("connection", ["control", "data"])
def test_close_failure_is_logged_and_preserves_source_error(ftp, connection, caplog):
    target = ftp if connection == "control" else ftp.transfercmd.return_value
    target.close.side_effect = OSError("close failed")
    with pytest.raises(RuntimeError, match="source failed"):
        with FtpUploader(settings()):
            raise RuntimeError("source failed")
    ftp.close.assert_called_once()
    ftp.transfercmd.return_value.close.assert_called_once()
    assert "close failed" in caplog.text


def test_main_exports_csv_to_ftp(tmp_path, monkeypatch, ftp):
    source = tmp_path / "input.csv"
    source.write_text("id,name\n1,café\n", encoding="utf-8")
    for key, value in {
        "SOURCE_PATH": str(source),
        "DESTINATION_TYPE": "ftp",
        "DESTINATION_PATH": "/exports/report.csv",
        "FTP_HOST": "localhost",
        "FTP_USER": "exporter",
        "FTP_PASSWORD": "secret",
    }.items():
        monkeypatch.setenv(key, value)
    main()
    payload = b"".join(
        bytes(call.args[0]) for call in ftp.transfercmd.return_value.sendall.call_args_list
    )
    assert payload.decode("utf-8") == "id,name\r\n1,café\r\n"
    ftp.rename.assert_called_once()

