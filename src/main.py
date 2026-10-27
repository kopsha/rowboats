#!/usr/bin/env python3

from itertools import chain
from logging import getLogger
from os import environ

import journal
from local import CsvSource, FileUploader, LocalSettings
from serializers import csv_serializer
from streamers import chunk_streamer


def main():
    """Serialize source rows as CSV and send buffered chunks to the uploader."""

    settings = LocalSettings.from_environment()

    with FileUploader(settings) as dest, CsvSource(settings) as source:
        rows = chain((source.columns(),), source.rows())
        records = map(csv_serializer, rows)
        chunks = chunk_streamer(records, dest.UPLOAD_THRESHOLD)
        for chunk in chunks:
            dest.send(chunk)


if __name__ == "__main__":
    from time import perf_counter

    journal.configure(
        level=environ.get("LOG_LEVEL", "INFO"),
        environment=environ.get("CONTEXT"),
        service="rowboats",
    )

    log = getLogger("main")
    start = perf_counter()

    main()

    took = perf_counter() - start
    log.info("CSV export completed in %.3fs", took)
