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

The first intended use case is exporting Databricks data to AWS S3 for retail
media feeds. The streaming core is implemented; the Databricks and AWS adapters
are still to be added.
