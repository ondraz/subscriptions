#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["httpx>=0.27"]
# ///
"""Round-trip Grafana dashboards between the running instance and git.

Subcommands:
  pull  Export every dashboard from the Grafana API to
        deploy/compose/observability/grafana/dashboards/<slug>.json.
  diff  Pull each dashboard into a temp file and print a unified diff
        against the committed version (useful before `pull`).

Provisioning loads the JSON files on container start and re-reads them
every 30s (see deploy/compose/observability/grafana/provisioning/dashboards/).
Pulling is the inverse — take the DB-stored edits a user made in the UI
and write them back to the files so they can be committed.

Env:
  GRAFANA_URL             default http://localhost:3000
  GRAFANA_USER            default admin
  GRAFANA_ADMIN_PASSWORD  default admin
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS_DIR = REPO_ROOT / "deploy" / "compose" / "observability" / "grafana" / "dashboards"


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "dashboard"


def normalize(dashboard: dict) -> dict:
    """Strip runtime fields so diffs stay minimal across pulls."""
    dashboard = dict(dashboard)
    dashboard["id"] = None
    dashboard["version"] = 1
    # iteration number changes on every save; drop it.
    dashboard.pop("iteration", None)
    return dashboard


def fetch_dashboards(client: httpx.Client) -> list[dict]:
    # type=dash-db excludes folders; we take every dashboard we can see.
    r = client.get("/api/search", params={"type": "dash-db"})
    r.raise_for_status()
    return list(r.json())


def fetch_dashboard(client: httpx.Client, uid: str) -> dict:
    r = client.get(f"/api/dashboards/uid/{uid}")
    r.raise_for_status()
    return dict(r.json()["dashboard"])


def pull(client: httpx.Client) -> int:
    DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for entry in fetch_dashboards(client):
        uid = entry["uid"]
        title = entry["title"]
        dash = normalize(fetch_dashboard(client, uid))
        path = DASHBOARDS_DIR / f"{slugify(title)}.json"
        payload = json.dumps(dash, indent=2, sort_keys=True) + "\n"
        path.write_text(payload)
        print(f"  {path.relative_to(REPO_ROOT)}  ({title})")
        written += 1
    print(f"Pulled {written} dashboard(s) into {DASHBOARDS_DIR.relative_to(REPO_ROOT)}")
    return 0


def diff(client: httpx.Client) -> int:
    rc = 0
    for entry in fetch_dashboards(client):
        uid = entry["uid"]
        title = entry["title"]
        dash = normalize(fetch_dashboard(client, uid))
        path = DASHBOARDS_DIR / f"{slugify(title)}.json"
        payload = json.dumps(dash, indent=2, sort_keys=True) + "\n"

        if not path.exists():
            print(f"[new]      {title}  ({path.relative_to(REPO_ROOT)})")
            rc = 1
            continue

        current = path.read_text()
        if current == payload:
            continue

        rc = 1
        proc = subprocess.run(
            [
                "diff",
                "-u",
                "--label",
                f"git:{path.name}",
                "--label",
                f"grafana:{title}",
                str(path),
                "-",
            ],
            input=payload,
            text=True,
            capture_output=True,
            check=False,
        )
        print(proc.stdout, end="")
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cmd", choices=["pull", "diff"])
    args = parser.parse_args()

    base_url = os.environ.get("GRAFANA_URL", "http://localhost:3000")
    user = os.environ.get("GRAFANA_USER", "admin")
    password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "admin")

    with httpx.Client(base_url=base_url, auth=(user, password), timeout=15.0) as client:
        if args.cmd == "pull":
            return pull(client)
        return diff(client)


if __name__ == "__main__":
    sys.exit(main())
