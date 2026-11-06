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

To upload to FTP, select the FTP destination and provide connection credentials:

```sh
export SOURCE_PATH=input.csv DESTINATION_TYPE=ftp
export FTP_HOST=ftp.example.com FTP_USER=exporter FTP_PASSWORD='your-password'
export DESTINATION_PATH=/exports/output.csv
python3 src/main.py
```

`FTP_PORT` defaults to `21` and `FTP_TIMEOUT` to `30` seconds. FTP uses passive
mode and streams binary data over a single transfer. The remote directory must
already exist. A temporary file in that directory is renamed to the destination
after success; unfinished uploads may leave temporary files. Replacing an
existing destination depends on the FTP server's rename support. Plain FTP sends
credentials and data without encryption; this adapter does not support FTPS or SFTP.
Omit `DESTINATION_TYPE` (or set it to `file`) for local output.

To upload over SFTP, install the requirements (including Paramiko) and configure
the environment before running `python3 src/main.py`:

```text
SOURCE_PATH=input.csv
DESTINATION_TYPE=sftp
SFTP_HOST=sftp.example.com
SFTP_USER=exporter
SFTP_KEY_FILENAME=/run/secrets/sftp_key
SFTP_KNOWN_HOSTS=/run/secrets/known_hosts
DESTINATION_PATH=/exports/output.csv
SFTP_PORT=22
SFTP_TIMEOUT=30
```

Authentication uses `SFTP_PASSWORD` or `SFTP_KEY_FILENAME`. The known-hosts
file must contain the server's trusted host key; unknown or mismatched keys are
rejected. In containers, mount the key and known-hosts files at the configured
paths.

The adapter streams to a unique temporary file in the destination
directory, closes it, and publishes it with `posix_rename()` after a successful
export. The remote directory must already exist, and the server must support
the OpenSSH POSIX rename extension for publication, including replacement of an
existing destination. There is no fallback that deletes the existing destination. Failed
uploads attempt to remove the temporary file; connection failures may leave
it behind. See Paramiko's [SSH client documentation](https://docs.paramiko.org/en/stable/api/client.html)
and [SFTP documentation](https://docs.paramiko.org/en/stable/api/sftp.html).

Databricks and AWS S3 adapters can later use the same interfaces without changing
the streaming pipeline.
