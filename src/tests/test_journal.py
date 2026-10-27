import json
import logging
import sys

import pytest

from journal import JsonFormatter


@pytest.fixture
def formatter():
    return JsonFormatter("retail-media-feeds", banner="example-banner", environment="production")


def test_formats_record_as_one_json_line(formatter):
    record = logging.LogRecord("feeds.export", logging.INFO, __file__, 1,
                               "Processed %s rows\nfor café", (42,), None)
    record.created = 0.123

    output = formatter.format(record)

    assert len(output.splitlines()) == 1
    assert json.loads(output) == {
        "timestamp": "1970-01-01T00:00:00.123Z",
        "level": "INFO",
        "logger": "feeds.export",
        "service": "retail-media-feeds",
        "banner": "example-banner",
        "env": "production",
        "message": "Processed 42 rows\nfor café",
    }


def test_includes_custom_extra_fields(formatter):
    record = logging.getLogger("feeds.export").makeRecord(
        "feeds.export", logging.INFO, __file__, 1, "Processed feed", (), None,
        extra={"feed_id": "abc", "rows": 42, "metadata": {"region": "eu"}},
    )

    result = json.loads(formatter.format(record))

    assert result["feed_id"] == "abc"
    assert result["rows"] == 42
    assert result["metadata"] == {"region": "eu"}


@pytest.mark.parametrize("field", ["timestamp", "level", "logger", "service", "banner", "env"])
def test_extra_fields_cannot_override_core_fields(formatter, field):
    record = logging.LogRecord("feeds.export", logging.INFO, __file__, 1, "Processed", (), None)
    expected = json.loads(formatter.format(record))[field]
    setattr(record, field, "override")

    assert json.loads(formatter.format(record))[field] == expected


@pytest.mark.parametrize("field", ["banner", "env"])
def test_optional_fields_default_to_null(field):
    formatter = JsonFormatter("retail-media-feeds")
    record = logging.LogRecord("feeds.export", logging.INFO, __file__, 1, "Processed", (), None)

    assert json.loads(formatter.format(record))[field] is None


def test_includes_exception_traceback(formatter):
    try:
        raise ValueError("Invalid feed")
    except ValueError:
        record = logging.LogRecord(
            "feeds.export", logging.ERROR, __file__, 1, "Export failed", (), sys.exc_info()
        )

    output = formatter.format(record)
    result = json.loads(output)

    assert len(output.splitlines()) == 1
    assert result["message"] == "Export failed"
    assert result["exception"].startswith("Traceback (most recent call last):\n")
    assert result["exception"].endswith("ValueError: Invalid feed")
