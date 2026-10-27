import csv
import io
from itertools import chain
from typing import Iterable, Iterator

from contracts import ChunkUploader, TableSource
from serializers import csv_serializer
from streamers import chunk_streamer


class GeneratedSource(TableSource):
    """Generate deterministic rows without storing the whole table."""

    def __init__(self, row_count: int):
        self.row_count = row_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def columns(self) -> Iterable[str]:
        return ("id", "name", "description")

    def rows(self) -> Iterator:
        for index in range(self.row_count):
            yield (
                index,
                f"Organization {index}",
                'Text with commas, "quotes", Unicode: café, and a\nnewline',
            )


class MemoryUploader(ChunkUploader):
    """Collect exported bytes and chunk sizes for inspection."""

    UPLOAD_THRESHOLD = 64 * 1024

    def __init__(self):
        self.buffer = io.BytesIO()
        self.chunk_sizes = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def send(self, chunk: memoryview) -> None:
        self.chunk_sizes.append(len(chunk))
        self.buffer.write(chunk)


def test_main():
    row_count = 10_000
    uploader = MemoryUploader()
    generated_source = GeneratedSource(row_count)

    with uploader as dest, generated_source as source:
        all_rows = chain((source.columns(),), source.rows())
        records = map(csv_serializer, all_rows)
        chunks = chunk_streamer(records, dest.UPLOAD_THRESHOLD)
        for chunk in chunks:
            dest.send(chunk)

    assert len(uploader.chunk_sizes) > 1
    assert all(size >= uploader.UPLOAD_THRESHOLD for size in uploader.chunk_sizes[:-1])
    assert 0 < uploader.chunk_sizes[-1] < uploader.UPLOAD_THRESHOLD
    assert sum(uploader.chunk_sizes) == uploader.buffer.tell()

    uploader.buffer.seek(0)
    with io.TextIOWrapper(uploader.buffer, encoding="utf-8", newline="") as output:
        reader = csv.reader(output)
        assert next(reader) == ["id", "name", "description"]
        for index in range(row_count):
            assert next(reader) == [
                str(index),
                f"Organization {index}",
                'Text with commas, "quotes", Unicode: café, and a\nnewline',
            ]
        assert next(reader, None) is None
