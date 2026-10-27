import csv
import io
from typing import Iterable


def csv_serializer(values: Iterable) -> bytes:
    """Encode one record as UTF-8 CSV bytes."""
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(values)
    return stream.getvalue().encode("utf-8")
