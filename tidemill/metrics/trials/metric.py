"""TrialsMetric — query methods and event handler.

Trial metrics are **cohort-based**: a trial is attributed to the period of
its ``started_at``, and its converted/expired outcome rolls up to the same
cohort no matter when the outcome event arrives.  This mirrors how SaaS
analytics tools like ChartMogul track trials and means a January-cohort
conversion rate can still move after the month closes (a March conversion
updates January's number).

The per-trial outcome is materialised in ``metric_trial`` (one row per
subscription that entered trialing); ``metric_trial_event`` is retained as
an append-only audit log.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from tidemill.metrics.base import Metric, QuerySpec
from tidemill.metrics.registry import register
from tidemill.metrics.trials.cubes import TrialCube
from tidemill.segments.compiler import build_spec_fragment

if TYPE_CHECKING:
    from datetime import date

    from fastapi import APIRouter

    from tidemill.events import Event

_EVENT_TYPE_MAP = {
    "subscription.trial_started": "started",
    "subscription.trial_converted": "converted",
    "subscription.trial_expired": "expired",
}


@register
class TrialsMetric(Metric):
    name = "trials"
    model = TrialCube

    @property
    def router(self) -> APIRouter:
        from tidemill.metrics.trials.routes import router

        return router

    @property
    def event_types(self) -> list[str]:
        return [
            "subscription.trial_started",
            "subscription.trial_converted",
            "subscription.trial_expired",
        ]

    async def handle_event(self, event: Event) -> None:
        p = event.payload
        event_type = _EVENT_TYPE_MAP.get(event.type)
        if event_type is None:
            return
        sub_id = p.get("external_id", "")

        await self.db.execute(
            text(
                "INSERT INTO metric_trial_event"
                " (id, event_id, source_id, customer_id,"
                "  subscription_id, event_type, occurred_at)"
                " VALUES (:id, :eid, :src, :cid, :sid, :et, :at)"
                " ON CONFLICT (event_id) DO NOTHING"
            ),
            {
                "id": str(uuid.uuid4()),
                "eid": event.id,
                "src": event.source_id,
                "cid": event.customer_id,
                "sid": sub_id,
                "et": event_type,
                "at": event.occurred_at,
            },
        )

        await self._upsert_trial(
            event_type=event_type,
            source_id=event.source_id,
            customer_id=event.customer_id,
            subscription_id=sub_id,
            occurred_at=event.occurred_at,
        )

    async def _upsert_trial(
        self,
        *,
        event_type: str,
        source_id: str,
        customer_id: str,
        subscription_id: str,
        occurred_at: Any,
    ) -> None:
        """Upsert a row in ``metric_trial``.

        Invariants:
        - ``started_at`` is the earliest observed start (LEAST of existing
          value and the incoming one) so out-of-order or late-arriving
          ``started`` events never overwrite a newer real start.
        - ``converted_at`` / ``expired_at`` are set once and never cleared.
          If both arrive (e.g. an erroneous ``expired`` after a genuine
          ``converted``), ``COALESCE`` keeps the earlier-written value.
        - A ``converted`` or ``expired`` event may arrive before the
          ``started`` event; we insert a placeholder row with
          ``started_at = occurred_at`` which the later ``started`` event
          will correct via ``LEAST(...)``.
        """
        col_map = {
            "started": "started_at",
            "converted": "converted_at",
            "expired": "expired_at",
        }
        col = col_map[event_type]

        if event_type == "started":
            sql = (
                "INSERT INTO metric_trial"
                " (id, source_id, customer_id, subscription_id, started_at)"
                " VALUES (:id, :src, :cid, :sid, :at)"
                " ON CONFLICT ON CONSTRAINT uq_trial_sub DO UPDATE SET"
                "   started_at = LEAST(metric_trial.started_at, EXCLUDED.started_at)"
            )
        else:
            sql = (
                "INSERT INTO metric_trial"
                f" (id, source_id, customer_id, subscription_id, started_at, {col})"
                " VALUES (:id, :src, :cid, :sid, :at, :at)"
                " ON CONFLICT ON CONSTRAINT uq_trial_sub DO UPDATE SET"
                f"   {col} = COALESCE(metric_trial.{col}, EXCLUDED.{col})"
            )

        await self.db.execute(
            text(sql),
            {
                "id": str(uuid.uuid4()),
                "src": source_id,
                "cid": customer_id,
                "sid": subscription_id,
                "at": occurred_at,
            },
        )

    async def query(self, params: dict[str, Any], spec: QuerySpec | None = None) -> Any:
        match params.get("query_type"):
            case "conversion_rate":
                return await self._conversion_rate(params["start"], params["end"], spec)
            case "series":
                return await self._conversion_series(
                    params["start"],
                    params["end"],
                    params.get("interval", "month"),
                    spec,
                )
            case "funnel":
                return await self._funnel(params["start"], params["end"], spec)
            case other:
                raise ValueError(f"Unknown query_type: {other}")

    async def _conversion_rate(
        self,
        start: date,
        end: date,
        spec: QuerySpec | None,
    ) -> Any:
        """Cohort trial conversion rate.

        Denominator is trials **started** in ``[start, end]`` (closed-closed —
        both endpoints inclusive, see ``docs/definitions.md``). Numerator is
        how many of those later converted (at any time — may be after
        ``end``). Returns None when no trials started in the range.

        With ``spec.compare`` set, returns a list of
        ``{segment_id, conversion_rate}`` dicts.
        """
        data = await self._funnel(start, end, spec)
        if isinstance(data, list):
            return [
                {"segment_id": e["segment_id"], "conversion_rate": e["conversion_rate"]}
                for e in data
            ]
        return data["conversion_rate"]

    async def _funnel(
        self,
        start: date,
        end: date,
        spec: QuerySpec | None,
    ) -> Any:
        """Cohort trial funnel: started, converted, expired counts.

        With ``spec.compare`` set, returns ``[{segment_id, started, converted,
        expired, conversion_rate}, ...]`` so per-segment rates are based on
        per-segment denominators.
        """
        m = self.model

        q = (
            m.measures.started_count
            + m.measures.converted_count
            + m.measures.expired_count
            + m.filter("started_at", "between", (start, end))
        )
        q = q + await build_spec_fragment(m, spec, self.db)

        stmt, params = q.compile(m)
        rows = (await self.db.execute(stmt, params)).mappings().all()

        if spec and spec.compare:
            by_seg = {r["segment_id"]: r for r in rows}
            out = []
            for seg_id, _ in spec.compare:
                r = by_seg.get(seg_id)
                if r is None:
                    out.append(
                        {
                            "segment_id": seg_id,
                            "started": 0,
                            "converted": 0,
                            "expired": 0,
                            "conversion_rate": None,
                        }
                    )
                    continue
                started = r["started"]
                converted = r["converted"]
                expired = r["expired"]
                out.append(
                    {
                        "segment_id": seg_id,
                        "started": started,
                        "converted": converted,
                        "expired": expired,
                        "conversion_rate": converted / started if started else None,
                    }
                )
            return out

        row = rows[0] if rows else None
        started = row["started"] if row else 0
        converted = row["converted"] if row else 0
        expired = row["expired"] if row else 0

        return {
            "started": started,
            "converted": converted,
            "expired": expired,
            "conversion_rate": converted / started if started else None,
        }

    async def _conversion_series(
        self,
        start: date,
        end: date,
        interval: str,
        spec: QuerySpec | None,
    ) -> list[dict[str, Any]]:
        """Cohort conversion rate per period, grouped by month (or other grain).

        Each row is a **started-in-period** cohort with its eventual
        outcomes (which may have occurred after ``end``).
        """
        m = self.model

        q = (
            m.measures.started_count
            + m.measures.converted_count
            + m.measures.expired_count
            + m.filter("started_at", "between", (start, end))
            + m.time_grain("started_at", interval)
        )
        q = q + await build_spec_fragment(m, spec, self.db)

        stmt, params = q.compile(m)
        result = await self.db.execute(stmt, params)

        series = []
        for r in result.mappings().all():
            started = r["started"]
            converted = r["converted"]
            expired = r["expired"]
            series.append(
                {
                    "period": str(r["period"]),
                    "started": started,
                    "converted": converted,
                    "expired": expired,
                    "conversion_rate": converted / started if started else None,
                }
            )
        series.sort(key=lambda row: row["period"])
        return series
