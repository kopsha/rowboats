import csv

import pytest

from local import FileUploader, LocalSettings
from main import main


def test_local_export(tmp_path, monkeypatch):
    source = tmp_path / "input.csv"
    destination = tmp_path / "output.csv"
    rows = [["id", "description"]] + [
        [str(index), 'Text with commas, "quotes", café\nand a newline']
        for index in range(5000)
    ]
    with source.open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream).writerows(rows)
    monkeypatch.setenv("SOURCE_PATH", str(source))
    monkeypatch.setenv("DESTINATION_PATH", str(destination))

    main()

    with destination.open(encoding="utf-8", newline="") as stream:
        assert list(csv.reader(stream)) == rows
    assert sorted(path.name for path in tmp_path.iterdir()) == ["input.csv", "output.csv"]


def test_failed_export_preserves_destination(tmp_path, monkeypatch):
    source = tmp_path / "missing.csv"
    destination = tmp_path / "output.csv"
    destination.write_bytes(b"previous export")
    monkeypatch.setenv("SOURCE_PATH", str(source))
    monkeypatch.setenv("DESTINATION_PATH", str(destination))

    with pytest.raises(FileNotFoundError):
        main()

    assert destination.read_bytes() == b"previous export"
    assert list(tmp_path.iterdir()) == [destination]


def test_failed_upload_discards_partial_file(tmp_path):
    destination = tmp_path / "output.csv"
    settings = LocalSettings(tmp_path / "input.csv", destination)

    with pytest.raises(RuntimeError, match="export failed"):
        with FileUploader(settings) as uploader:
            uploader.send(memoryview(b"partial"))
            raise RuntimeError("export failed")

    assert list(tmp_path.iterdir()) == []
