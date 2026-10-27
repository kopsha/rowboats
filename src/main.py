#!/usr/bin/env python3

from itertools import chain
from logging import getLogger
from os import environ

import journal
from serializers import csv_serializer
from streamers import chunk_streamer


def main():
    """Serialize source rows as CSV and send buffered chunks to the uploader."""

    nucleus_config = DatabricksSettings.from_environment()
    nucleus_client = DatabricksSource(nucleus_config)

    aws_config = AwsSettings.from_environment()
    s3_bucket = AwsStorage(aws_config)

    with s3_bucket as dest, nucleus_client as source:
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
        service="retail-media-feeds",
    )

    log = getLogger("main")
    start = perf_counter()

    main()

    took = perf_counter() - start
    log.info("Instore feeds export completed in %.3fs", took)
