"""Local CSV table source using only the standard library."""

import csv

from contracts import TableSource
from local import LocalSettings


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
