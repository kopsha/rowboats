"""Configure application logging as one-JSON-object-per-line records."""

import json
import logging
import sys
from datetime import datetime, timezone

_STANDARD_FIELDS = set(logging.makeLogRecord({}).__dict__)


class JsonFormatter(logging.Formatter):
    """Format a log record as a JSON object suitable for log ingestion."""

    def __init__(self, service, *, environment=None):
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record):
        log = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "environment": self.environment,
            "message": record.getMessage(),
        }

        log.update(
            (key, value)
            for key, value in record.__dict__.items()
            if key not in _STANDARD_FIELDS and key not in log
        )

        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log["stack"] = self.formatStack(record.stack_info)

        return json.dumps(log, default=str, ensure_ascii=False)


def configure(level="INFO", *, service, environment=None):
    """Configure root logging to write structured JSON records to stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service, environment=environment))
    logging.basicConfig(level=level, handlers=[handler], force=True)
