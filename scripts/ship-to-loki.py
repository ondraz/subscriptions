#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["httpx>=0.27"]
# ///
r"""Tee stdin to stdout and ship every line to Loki.

Used to pipe locally-run tidemill API/worker logs into Loki so they show
up alongside containerized services in Grafana. Trace ID / span ID / log
level are extracted from the ``DefaultFormatter`` output and attached as
labels, so Grafana's trace→log correlation works for host-run processes.

Example:
    uv run uvicorn tidemill.api.app:app --host 0.0.0.0 --port 8000 --reload 2>&1 \\
        | scripts/ship-to-loki.py --service tidemill-api

    uv run python -m tidemill.worker 2>&1 \\
        | scripts/ship-to-loki.py --service tidemill-worker

Env:
    LOKI_URL  default http://localhost:3100
"""

from __future__ import annotations

import argparse
import os
import re
import signal
import sys
import threading
import time
from queue import Empty, Queue

import httpx

# Strip ANSI color/style escapes that uvicorn's DefaultFormatter emits.
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
TRACE_RE = re.compile(r"trace_id=(?P<trace_id>[0-9a-f]+)\s+span_id=(?P<span_id>[0-9a-f]+)")
LEVEL_RE = re.compile(r"\b(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\b")


def extract_labels(service: str, line: str) -> dict[str, str]:
    labels = {"service": service, "source": "host"}
    if m := TRACE_RE.search(line):
        labels["trace_id"] = m.group("trace_id")
        labels["span_id"] = m.group("span_id")
    if m := LEVEL_RE.search(line):
        labels["level"] = m.group("level").lower()
    return labels


def shipper_loop(
    url: str,
    queue: Queue[tuple[float, dict[str, str], str]],
    stop: threading.Event,
) -> None:
    with httpx.Client(timeout=5.0) as client:
        while not stop.is_set() or not queue.empty():
            batch: list[tuple[float, dict[str, str], str]] = []
            deadline = time.monotonic() + 1.0
            while len(batch) < 500:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    batch.append(queue.get(timeout=remaining))
                except Empty:
                    break
            if not batch:
                continue

            streams: dict[tuple[tuple[str, str], ...], list[list[str]]] = {}
            for ts, labels, line in batch:
                key = tuple(sorted(labels.items()))
                streams.setdefault(key, []).append([str(int(ts * 1e9)), line])

            body = {
                "streams": [{"stream": dict(k), "values": v} for k, v in streams.items()],
            }
            try:
                resp = client.post(f"{url}/loki/api/v1/push", json=body)
                if resp.status_code >= 300:
                    sys.stderr.write(
                        f"[ship-to-loki] push {resp.status_code}: {resp.text[:200]}\n",
                    )
            except Exception as exc:
                sys.stderr.write(f"[ship-to-loki] push failed: {exc}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        required=True,
        help="service label, e.g. tidemill-api or tidemill-worker",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("LOKI_URL", "http://localhost:3100"),
    )
    args = parser.parse_args()

    queue: Queue[tuple[float, dict[str, str], str]] = Queue()
    stop = threading.Event()

    t = threading.Thread(
        target=shipper_loop,
        args=(args.url, queue, stop),
        daemon=True,
    )
    t.start()

    def handle_signal(signum: int, frame: object) -> None:
        stop.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    for raw in sys.stdin:
        line = raw.rstrip("\n")
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

        clean = ANSI_RE.sub("", line)
        queue.put((time.time(), extract_labels(args.service, clean), clean))

    stop.set()
    t.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
