# rowboats

Generic rows on their way somewhere.

Rowboats streams tabular data from a source to a destination. It reads rows,
serializes them as CSV, and uploads them in buffered chunks without loading the
whole table into memory.

```text
Table source → header and rows → CSV records → buffered chunks → destination
```

Sources provide ordered column names and rows. Uploaders receive chunks in order
and manage the upload lifecycle. These interfaces keep the export pipeline
independent of any particular database or storage service.

The runnable example reads a local CSV file and writes it to another file using
only Python's standard library. The first row supplies the column names. The
destination is replaced only after the export succeeds.

```sh
SOURCE_PATH=input.csv DESTINATION_PATH=output.csv python3 src/main.py
```

The input must contain a header, and the destination directory must already exist.
CSV values are preserved, but quoting and line endings may be normalized.

Databricks and AWS S3 adapters can later use the same interfaces without changing
the streaming pipeline.
