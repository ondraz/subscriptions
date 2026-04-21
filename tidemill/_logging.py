"""Shared stdout logging setup for API and worker processes."""

from __future__ import annotations

import logging
import os


class _TraceContextFilter(logging.Filter):
    """Provide empty-string fallbacks for OTEL log record fields.

    LoggingInstrumentor attaches otelTraceID/otelSpanID/otelServiceName via a
    record factory when tracing is active. When OTEL is disabled those fields
    are missing and %-formatting would raise. This filter injects empty
    defaults so the same format string works in both modes.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in ("otelTraceID", "otelSpanID", "otelServiceName"):
            if not hasattr(record, attr):
                setattr(record, attr, "")
        return True


def configure_logging(service_name: str) -> None:
    """Configure the `tidemill` logger with a shared formatter."""
    log_level = os.environ.get("TIDEMILL_LOG_LEVEL", "DEBUG").upper()

    from uvicorn.logging import DefaultFormatter

    handler = logging.StreamHandler()
    handler.setFormatter(
        DefaultFormatter(
            fmt=(
                "%(levelprefix)s %(name)s "
                "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] - %(message)s"
            ),
        ),
    )
    handler.addFilter(_TraceContextFilter())

    logger = logging.getLogger("tidemill")
    logger.setLevel(getattr(logging, log_level, logging.DEBUG))
    # Replace any previously installed handlers so re-invocation is idempotent.
    for h in list(logger.handlers):
        logger.removeHandler(h)
    logger.addHandler(handler)
    logger.propagate = False

    logger.debug("Logging configured for service=%s", service_name)
