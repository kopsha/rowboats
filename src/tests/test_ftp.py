from unittest.mock import Mock

import pytest

from ftp import FtpSettings, FtpUploader
from main import main


@pytest.fixture
def ftp(monkeypatch):
    client = Mock()
    monkeypatch.setattr("ftp.FTP", lambda: client)
    return client


def settings():
    return FtpSettings("localhost", "exporter", "secret", "/exports/report.csv")


def test_streams_binary_chunks_then_publishes(ftp):
    with FtpUploader(settings()) as uploader:
        uploader.send(memoryview(b"first"))
        uploader.send(memoryview(b"second"))
        ftp.rename.assert_not_called()
    ftp.connect.assert_called_once_with("localhost", 21, timeout=30)
    ftp.login.assert_called_once_with("exporter", "secret")
    ftp.voidcmd.assert_called_once_with("TYPE I")
    assert [call.args[0] for call in ftp.transfercmd.return_value.sendall.call_args_list] == [
        b"first",
        b"second",
    ]
    ftp.voidresp.assert_called_once()
    ftp.rename.assert_called_once_with(uploader.temporary_path, "/exports/report.csv")
    ftp.delete.assert_not_called()


@pytest.mark.parametrize("failure", ["source", "send", "transfer", "reply", "rename"])
def test_failed_export_discards_temporary_upload(ftp, failure):
    error = RuntimeError("export failed")
    if failure == "send":
        ftp.transfercmd.return_value.sendall.side_effect = error
    elif failure == "transfer":
        ftp.transfercmd.side_effect = error
    elif failure == "reply":
        ftp.voidresp.side_effect = error
    elif failure == "rename":
        ftp.rename.side_effect = error
    uploader = FtpUploader(settings())
    with pytest.raises(RuntimeError, match="export failed"):
        with uploader:
            uploader.send(memoryview(b"partial"))
            if failure == "source":
                raise error
    ftp.delete.assert_called_once_with(uploader.temporary_path)
    if failure != "rename":
        ftp.rename.assert_not_called()


def test_cleanup_failure_preserves_original_error(ftp):
    ftp.delete.side_effect = OSError("cleanup failed")
    with pytest.raises(RuntimeError, match="source failed"):
        with FtpUploader(settings()):
            raise RuntimeError("source failed")


def test_login_failure_closes_connection(ftp):
    ftp.login.side_effect = OSError("login failed")
    with pytest.raises(OSError, match="login failed"):
        with FtpUploader(settings()):
            pytest.fail("entry should fail")
    ftp.close.assert_called_once()


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


@pytest.mark.parametrize(
    "key,value",
    [
        ("FTP_PORT", "0"),
        ("FTP_TIMEOUT", "nan"),
        ("DESTINATION_PATH", "/exports/"),
        ("DESTINATION_PATH", "file\r\nDELE other"),
    ],
)
def test_rejects_invalid_settings(key, value):
    values = {
        "FTP_HOST": "localhost",
        "FTP_USER": "user",
        "FTP_PASSWORD": "secret",
        "DESTINATION_PATH": "report.csv",
        key: value,
    }
    with pytest.raises(ValueError):
        FtpSettings.from_values(values)
