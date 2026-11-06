from pathlib import PurePosixPath
from unittest.mock import Mock

import pytest
from paramiko import RejectPolicy, SSHClient

from main import main
from sftp import SftpSettings, SftpUploader


@pytest.fixture
def settings():
    return SftpSettings(
        "example.com",
        "exporter",
        "/known_hosts",
        PurePosixPath("/exports/output.csv"),
        password="secret",
    )


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    monkeypatch.setattr("sftp.SSHClient", lambda: client)
    return client


def test_success(settings, client):
    remote = client.open_sftp.return_value
    events = Mock()
    events.attach_mock(remote.open.return_value.close, "close_file")
    events.attach_mock(remote.posix_rename, "publish")
    with SftpUploader(settings) as uploader:
        uploader.send(memoryview(b"hello"))
        uploader.send(memoryview(b"world"))
    client.load_host_keys.assert_called_once_with("/known_hosts")
    kwargs = client.connect.call_args.kwargs
    assert kwargs["allow_agent"] is False
    assert kwargs["look_for_keys"] is False
    assert kwargs["password"] == "secret"
    remote.get_channel.return_value.settimeout.assert_called_once_with(30)
    remote.open.return_value.write.assert_any_call(b"hello")
    remote.open.return_value.write.assert_any_call(b"world")
    assert [call[0] for call in events.mock_calls] == ["close_file", "publish"]
    remote.posix_rename.assert_called_once_with(uploader.temporary_path, "/exports/output.csv")
    remote.remove.assert_not_called()
    remote.close.assert_called_once()
    client.close.assert_called_once()


@pytest.mark.parametrize("stage", ["write", "close", "rename", "body"])
def test_failed_export_discards_temporary_file(settings, client, stage):
    remote = client.open_sftp.return_value
    error = RuntimeError(stage)
    if stage == "write":
        remote.open.return_value.write.side_effect = error
    elif stage == "close":
        remote.open.return_value.close.side_effect = error
    elif stage == "rename":
        remote.posix_rename.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        with SftpUploader(settings) as uploader:
            uploader.send(memoryview(b"partial"))
            if stage == "body":
                raise error
    assert caught.value is error
    remote.remove.assert_called_once_with(uploader.temporary_path)
    if stage != "rename":
        remote.posix_rename.assert_not_called()
    remote.close.assert_called_once()
    client.close.assert_called_once()


@pytest.mark.parametrize("stage", ["host_keys", "connect", "session", "open"])
def test_failed_entry_closes_acquired_resources(settings, client, stage):
    remote = client.open_sftp.return_value
    target = {
        "host_keys": client.load_host_keys,
        "connect": client.connect,
        "session": client.open_sftp,
        "open": remote.open,
    }[stage]
    target.side_effect = OSError(stage)
    with pytest.raises(OSError, match=stage):
        with SftpUploader(settings):
            pytest.fail("entry should fail")
    client.close.assert_called_once()
    if stage == "open":
        remote.close.assert_called_once()
    remote.remove.assert_not_called()


def test_cleanup_failures_preserve_original_error(settings, client, caplog):
    remote = client.open_sftp.return_value
    remote.open.return_value.close.side_effect = OSError("close failed")
    remote.remove.side_effect = OSError("remove failed")
    remote.close.side_effect = OSError("session close failed")
    client.close.side_effect = OSError("ssh close failed")
    with pytest.raises(RuntimeError, match="original"):
        with SftpUploader(settings):
            raise RuntimeError("original")
    assert "remove failed" in caplog.text
    client.close.assert_called_once()


def test_settings(monkeypatch):
    values = {
        "SFTP_HOST": "host",
        "SFTP_USER": "user",
        "SFTP_KNOWN_HOSTS": "/hosts",
        "DESTINATION_PATH": "/out.csv",
        "SFTP_KEY_FILENAME": "/key",
        "SFTP_PORT": "2222",
        "SFTP_TIMEOUT": "12.5",
    }
    monkeypatch.setattr("settings.environ", values)
    settings = SftpSettings.from_environment()
    assert settings.port == 2222
    assert settings.timeout == 12.5
    assert settings.key_filename == "/key"
    assert settings.password is None
    values.pop("SFTP_KEY_FILENAME")
    with pytest.raises(ValueError, match="SFTP_PASSWORD or SFTP_KEY_FILENAME"):
        SftpSettings.from_environment()
    values["SFTP_PASSWORD"] = "secret"
    assert "secret" not in repr(SftpSettings.from_environment())


def test_unknown_hosts_are_rejected():
    client = SSHClient()
    assert isinstance(client._policy, RejectPolicy)


def test_main_routes_sftp(tmp_path, monkeypatch, client):
    source = tmp_path / "input.csv"
    source.write_text("id,name\n1,Alice\n")
    values = {
        "SOURCE_PATH": str(source),
        "DESTINATION_TYPE": "sftp",
        "SFTP_HOST": "host",
        "SFTP_USER": "user",
        "SFTP_PASSWORD": "secret",
        "SFTP_KNOWN_HOSTS": "/hosts",
        "DESTINATION_PATH": "/out.csv",
    }
    monkeypatch.setattr("main.environ", values)
    monkeypatch.setattr("settings.environ", values)
    main()
    remote = client.open_sftp.return_value
    data = b"".join(call.args[0] for call in remote.open.return_value.write.call_args_list)
    assert data == b"id,name\r\n1,Alice\r\n"
    remote.posix_rename.assert_called_once()
