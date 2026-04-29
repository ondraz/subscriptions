"""ChurnMetric — query methods and event handler."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from tidemill.metrics.base import Metric, QuerySpec
from tidemill.metrics.churn.cubes import ChurnCustomerStateCube, ChurnEventCube
from tidemill.metrics.registry import register
from tidemill.segments.compiler import build_spec_fragment

if TYPE_CHECKING:
    from datetime import date

    from fastapi import APIRouter

    from tidemill.events import Event


@register
class ChurnMetric(Metric):
    name = "churn"
    event_model = ChurnEventCube
    state_model = ChurnCustomerStateCube

    @property
    def router(self) -> APIRouter:
        from tidemill.metrics.churn.routes import router

        return router

    @property
    def primary_cube(self) -> type[ChurnEventCube]:
        # Event cube carries the cancel_reason / churn_type / customer dims
        # that users want to slice by; the state cube is an internal join target.
        return self.event_model

    @property
    def event_types(self) -> list[str]:
        return [
            "subscription.created",
            "subscription.activated",
            "subscription.reactivated",
            "subscription.churned",
            "subscription.canceled",
        ]

    async def handle_event(self, event: Event) -> None:
        p = event.payload

        match event.type:
            case "subscription.created":
                # Ensure customer row exists but don't increment counter.
                # The counter is incremented by subscription.activated —
                # created + activated both fire for the same sub, so
                # incrementing on both would inflate the count.
                await self.db.execute(
                    text(
                        "INSERT INTO metric_churn_customer_state"
                        " (id, source_id, customer_id, active_subscriptions,"
                        "  first_active_at)"
                        " VALUES (:id, :src, :cid, 0, :now)"
                        " ON CONFLICT ON CONSTRAINT uq_churn_state_customer"
                        " DO NOTHING"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "src": event.source_id,
                        "cid": event.customer_id,
                        "now": event.occurred_at,
                    },
                )

            case "subscription.activated" | "subscription.reactivated":
                sub_id = p["external_id"]
                # Track this subscription as active; skip if already tracked
                # (idempotent — duplicate Kafka deliveries won't double-count)
                result = await self.db.execute(
                    text(
                        "INSERT INTO metric_churn_active_subscription"
                        " (id, source_id, customer_id, subscription_id)"
                        " VALUES (:id, :src, :cid, :sid)"
                        " ON CONFLICT ON CONSTRAINT uq_churn_active_sub"
                        " DO NOTHING"
                        " RETURNING id"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "src": event.source_id,
                        "cid": event.customer_id,
                        "sid": sub_id,
                    },
                )
                if result.fetchone() is None:
                    # Duplicate — subscription already counted, just clear churned_at
                    await self.db.execute(
                        text(
                            "UPDATE metric_churn_customer_state"
                            " SET churned_at = NULL"
                            " WHERE source_id = :src AND customer_id = :cid"
                        ),
                        {"src": event.source_id, "cid": event.customer_id},
                    )
                else:
                    # New activation — increment counter
                    await self.db.execute(
                        text(
                            "INSERT INTO metric_churn_customer_state"
                            " (id, source_id, customer_id, active_subscriptions,"
                            "  first_active_at)"
                            " VALUES (:id, :src, :cid, 1, :now)"
                            " ON CONFLICT ON CONSTRAINT uq_churn_state_customer"
                            " DO UPDATE SET"
                            "  active_subscriptions ="
                            "    metric_churn_customer_state.active_subscriptions + 1,"
                            "  first_active_at = COALESCE("
                            "    metric_churn_customer_state.first_active_at,"
                            "    EXCLUDED.first_active_at),"
                            "  churned_at = NULL"
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "src": event.source_id,
                            "cid": event.customer_id,
                            "now": event.occurred_at,
                        },
                    )

            case "subscription.churned":
                sub_id = p["external_id"]
                # Remove subscription from active set; skip if already removed
                # (idempotent — duplicate deliveries won't double-decrement)
                removed = await self.db.execute(
                    text(
                        "DELETE FROM metric_churn_active_subscription"
                        " WHERE source_id = :src"
                        "   AND customer_id = :cid"
                        "   AND subscription_id = :sid"
                        " RETURNING id"
                    ),
                    {
                        "src": event.source_id,
                        "cid": event.customer_id,
                        "sid": sub_id,
                    },
                )
                if removed.fetchone() is not None:
                    # Decrement active count
                    await self.db.execute(
                        text(
                            "UPDATE metric_churn_customer_state SET"
                            "  active_subscriptions ="
                            "    GREATEST(active_subscriptions - 1, 0)"
                            " WHERE source_id = :src AND customer_id = :cid"
                        ),
                        {"src": event.source_id, "cid": event.customer_id},
                    )
                # Check if fully churned (0 active) → set churned_at + logo event
                result = await self.db.execute(
                    text(
                        "UPDATE metric_churn_customer_state"
                        " SET churned_at = :now"
                        " WHERE source_id = :src AND customer_id = :cid"
                        "   AND active_subscriptions = 0"
                        " RETURNING id"
                    ),
                    {
                        "src": event.source_id,
                        "cid": event.customer_id,
                        "now": event.occurred_at,
                    },
                )
                if result.fetchone() is not None:
                    await self.db.execute(
                        text(
                            "INSERT INTO metric_churn_event"
                            " (id, event_id, source_id, customer_id,"
                            "  churn_type, cancel_reason, mrr_cents, occurred_at)"
                            " VALUES (:id, :eid, :src, :cid,"
                            "  'logo', :reason, :mrr, :now)"
                            " ON CONFLICT (event_id) DO NOTHING"
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "eid": event.id + ":logo",
                            "src": event.source_id,
                            "cid": event.customer_id,
                            "reason": p.get("cancel_reason"),
                            "mrr": p.get("prev_mrr_cents", 0),
                            "now": event.occurred_at,
                        },
                    )
                # Always record revenue churn event
                await self.db.execute(
                    text(
                        "INSERT INTO metric_churn_event"
                        " (id, event_id, source_id, customer_id,"
                        "  churn_type, cancel_reason, mrr_cents, occurred_at)"
                        " VALUES (:id, :eid, :src, :cid,"
                        "  'revenue', :reason, :mrr, :now)"
                        " ON CONFLICT (event_id) DO NOTHING"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "eid": event.id + ":revenue",
                        "src": event.source_id,
                        "cid": event.customer_id,
                        "reason": p.get("cancel_reason"),
                        "mrr": p.get("prev_mrr_cents", 0),
                        "now": event.occurred_at,
                    },
                )

            case "subscription.canceled":
                await self.db.execute(
                    text(
                        "INSERT INTO metric_churn_event"
                        " (id, event_id, source_id, customer_id,"
                        "  churn_type, cancel_reason, mrr_cents, occurred_at)"
                        " VALUES (:id, :eid, :src, :cid,"
                        "  'canceled', :reason, :mrr, :now)"
                        " ON CONFLICT (event_id) DO NOTHING"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "eid": event.id,
                        "src": event.source_id,
                        "cid": event.customer_id,
                        "reason": p.get("cancel_reason"),
                        "mrr": p.get("mrr_cents", 0),
                        "now": event.occurred_at,
                    },
                )

    async def query(self, params: dict[str, Any], spec: QuerySpec | None = None) -> Any:
        churn_type = params.get("type", "logo")
        start, end = params["start"], params["end"]

        match churn_type:
            case "logo":
                return await self._logo_churn(start, end, spec)
            case "revenue":
                return await self._revenue_churn(start, end, spec)
            case "detail":
                return await self._customer_detail(start, end, spec)
            case "revenue_events":
                return await self._revenue_events(start, end, spec)
            case other:
                raise ValueError(f"Unknown churn type: {other}")

    async def _logo_churn(
        self,
        start: date,
        end: date,
        spec: QuerySpec | None,
    ) -> Any:
        em = self.event_model
        has_compare = bool(spec and spec.compare)

        # Numerator: logo churn events scoped to customers active at period start
        q = (
            em.measures.count
            + em.filter("churn_type", "=", "logo")
            + em.filter("occurred_at", "between", (start, end))
            + em.filter("customer_first_active", "<", start)
        )
        q = q + await build_spec_fragment(em, spec, self.db)

        stmt, params = q.compile(em)
        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()

        if has_compare and spec is not None and spec.compare:
            # Per-segment: both numerator and denominator go through the
            # same compare fragment so rates are segment-specific (not a
            # shared denominator).
            churn_by_seg = {r["segment_id"]: int(r["churn_count"] or 0) for r in rows}
            active_by_seg = await self._active_at_start_count(start, spec)
            out = []
            for seg_id, _ in spec.compare:
                n = churn_by_seg.get(seg_id, 0)
                d = active_by_seg.get(seg_id, 0) if isinstance(active_by_seg, dict) else 0
                rate = float(n) / float(d) if d > 0 else None
                out.append(
                    {
                        "segment_id": seg_id,
                        "logo_churn_rate": rate,
                        "churn_count": n,
                        "active_at_start": d,
                    }
                )
            return out

        if spec and spec.dimensions:
            return [dict(r) for r in rows]

        churned = rows[0]["churn_count"] if rows else 0

        # Denominator: customers with positive MRR at period start.
        # Using MRR movements rather than the state table because
        # churned_at is cleared on reactivation, which mis-counts
        # customers who churned before start and later reactivated.
        active_start = await self._active_at_start_count(start, spec)
        if isinstance(active_start, dict):
            # Defensive — non-compare path should get a scalar.
            active_start = sum(active_start.values())

        if active_start == 0:
            return None
        return float(churned) / float(active_start)

    async def _revenue_churn(
        self,
        start: date,
        end: date,
        spec: QuerySpec | None,
    ) -> Any:
        em = self.event_model
        has_compare = bool(spec and spec.compare)

        # Numerator: churned MRR scoped to customers active at period start
        q = (
            em.measures.revenue_lost
            + em.filter("churn_type", "=", "revenue")
            + em.filter("occurred_at", "between", (start, end))
            + em.filter("customer_first_active", "<", start)
        )
        q = q + await build_spec_fragment(em, spec, self.db)

        stmt, params = q.compile(em)
        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()

        if has_compare and spec is not None and spec.compare:
            churn_by_seg = {r["segment_id"]: abs(float(r["revenue_lost"] or 0)) for r in rows}
            start_mrr_by_seg = await self._mrr_at_start_per_segment(start, spec)
            out = []
            for seg_id, _ in spec.compare:
                n = churn_by_seg.get(seg_id, 0.0)
                d = start_mrr_by_seg.get(seg_id, 0.0)
                rate = float(n) / float(d) if d > 0 else None
                out.append(
                    {
                        "segment_id": seg_id,
                        "revenue_churn_rate": rate,
                        "revenue_lost": n,
                        "start_mrr": d,
                    }
                )
            return out

        if spec and spec.dimensions:
            return [dict(r) for r in rows]

        churn_amount = abs(float(rows[0]["revenue_lost"] or 0)) if rows else 0

        # Denominator: MRR at period start = cumulative movements before start.
        # Same compare payload flows through build_spec_fragment so a segment
        # filter (non-compare) narrows the denominator too.
        from tidemill.metrics.mrr.cubes import MRRMovementCube

        mm = MRRMovementCube
        dq = mm.measures.amount + mm.filter("occurred_at", "<", start)
        dq = dq + await build_spec_fragment(mm, spec, self.db)
        dstmt, dparams = dq.compile(mm)
        dresult = await self.db.execute(dstmt, dparams)
        drows = dresult.mappings().all()
        start_mrr = float(drows[0]["amount_base"] or 0) if drows else 0

        if start_mrr == 0:
            return None
        return float(churn_amount) / float(start_mrr)

    async def _active_at_start_count(
        self,
        start: date,
        spec: QuerySpec | None = None,
    ) -> int | dict[str, int]:
        """Count customers with positive MRR at period start.

        Returns a scalar in the default path.  When ``spec.compare`` is set,
        returns ``{segment_id: count}`` so the ratio callers can divide
        per-segment.
        """
        from tidemill.metrics.mrr.cubes import MRRMovementCube

        mm = MRRMovementCube
        q = mm.dimension("customer_id") + mm.measures.amount + mm.filter("occurred_at", "<", start)
        q = q + await build_spec_fragment(mm, spec, self.db)
        stmt, params = q.compile(mm)
        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()

        if spec and spec.compare:
            counts: dict[str, int] = {}
            for r in rows:
                if int(r["amount_base"] or 0) > 0:
                    sid = r["segment_id"]
                    counts[sid] = counts.get(sid, 0) + 1
            return counts

        return sum(1 for r in rows if int(r["amount_base"] or 0) > 0)

    async def _mrr_at_start_per_segment(
        self,
        start: date,
        spec: QuerySpec | None,
    ) -> dict[str, float]:
        """Cumulative MRR at period start, summed per segment."""
        from tidemill.metrics.mrr.cubes import MRRMovementCube

        mm = MRRMovementCube
        q = mm.measures.amount + mm.filter("occurred_at", "<", start)
        q = q + await build_spec_fragment(mm, spec, self.db)
        stmt, params = q.compile(mm)
        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()
        return {r["segment_id"]: float(r["amount_base"] or 0) for r in rows}

    async def _customer_detail(
        self,
        start: date,
        end: date,
        spec: QuerySpec | None = None,
    ) -> list[dict[str, Any]]:
        """Per-customer churn breakdown for the period.

        Returns one row per customer who was active at period start, with
        their logo/revenue churn contributions and starting MRR. When ``spec``
        carries a segment filter, the four sub-queries are narrowed via the
        customer/customer_attribute join so customers outside the segment are
        excluded from every step (active set, logo events, revenue events,
        starting MRR). Compare mode is propagated as a universe filter only —
        the per-customer table doesn't slice into per-branch rows.
        """
        # Compare mode would expand the per-customer table to (customer ×
        # branch) which the chart can't consume; treat compare as a universe
        # union instead so the table stays one row per customer.
        from tidemill.metrics.retention.metric import _filter_only

        narrowed = _filter_only(spec)

        em = self.event_model
        sm = self.state_model

        # 1. Customers active at start (with name)
        aq = (
            sm.dimension("customer_id")
            + sm.dimension("customer_name")
            + sm.measures.count
            + sm.where("cs.first_active_at", "<", start)
            + sm.where("COALESCE(cs.churned_at, '9999-12-31'::timestamptz)", ">=", start)
        )
        aq = aq + await build_spec_fragment(sm, narrowed, self.db)
        astmt, aparams = aq.compile(sm)
        aresult = await self.db.execute(astmt, aparams)
        active_rows = aresult.mappings().all()
        active_customers = {r["customer_id"] for r in active_rows}
        name_by_cust = {r["customer_id"]: r["customer_name"] for r in active_rows}

        # 2. Logo churn events per customer (fully churned)
        lq = (
            em.dimension("customer_id")
            + em.measures.count
            + em.filter("churn_type", "=", "logo")
            + em.filter("occurred_at", "between", (start, end))
            + em.filter("customer_first_active", "<", start)
        )
        lq = lq + await build_spec_fragment(em, narrowed, self.db)
        lstmt, lparams = lq.compile(em)
        lresult = await self.db.execute(lstmt, lparams)
        logo_by_cust = {r["customer_id"]: int(r["churn_count"]) for r in lresult.mappings().all()}

        # 3. Revenue churn per customer
        rq = (
            em.dimension("customer_id")
            + em.measures.revenue_lost
            + em.filter("churn_type", "=", "revenue")
            + em.filter("occurred_at", "between", (start, end))
            + em.filter("customer_first_active", "<", start)
        )
        rq = rq + await build_spec_fragment(em, narrowed, self.db)
        rstmt, rparams = rq.compile(em)
        rresult = await self.db.execute(rstmt, rparams)
        rev_by_cust = {
            r["customer_id"]: abs(int(r["revenue_lost"] or 0)) for r in rresult.mappings().all()
        }

        # 4. Per-customer starting MRR (cumulative movements before start)
        from tidemill.metrics.mrr.cubes import MRRMovementCube

        mm = MRRMovementCube
        mq = (
            mm.dimension("customer_id") + mm.measures.amount + mm.filter("occurred_at", "<", start)
        )
        mq = mq + await build_spec_fragment(mm, narrowed, self.db)
        mstmt, mparams = mq.compile(mm)
        mresult = await self.db.execute(mstmt, mparams)
        mrr_by_cust = {
            r["customer_id"]: int(r["amount_base"] or 0) for r in mresult.mappings().all()
        }

        # Only include customers with positive starting MRR.
        # The state table stores *current* state — churned_at is cleared on
        # reactivation, so a customer who churned before `start` and later
        # reactivated would pass the state-table filter even though they were
        # not active at `start`.  MRR movements are event-sourced with
        # timestamps, so cumulative MRR < start == 0 is the reliable check.
        return [
            {
                "customer_id": cid,
                "customer_name": name_by_cust.get(cid),
                "active_at_start": True,
                "fully_churned": cid in logo_by_cust,
                "churned_mrr_cents": rev_by_cust.get(cid, 0),
                "starting_mrr_cents": mrr_by_cust.get(cid, 0),
            }
            for cid in sorted(active_customers)
            if mrr_by_cust.get(cid, 0) > 0
        ]

    async def _revenue_events(
        self,
        start: date,
        end: date,
        spec: QuerySpec | None = None,
    ) -> list[dict[str, Any]]:
        """Individual revenue-churn events for customers active at start.

        Returns one row per churn event with customer, name, MRR lost,
        and event timestamp. With a segment filter, both the event scan and
        the starting-MRR scan are narrowed so only events from in-segment
        customers are surfaced.
        """
        from tidemill.metrics.retention.metric import _filter_only

        narrowed = _filter_only(spec)

        em = self.event_model

        # Revenue churn events in window, scoped to active-at-start customers
        q = (
            em.dimension("customer_id")
            + em.dimension("customer_name")
            + em.measures.revenue_lost
            + em.measures.count
            + em.filter("churn_type", "=", "revenue")
            + em.filter("occurred_at", "between", (start, end))
            + em.filter("customer_first_active", "<", start)
        )
        q = q + await build_spec_fragment(em, narrowed, self.db)
        stmt, params = q.compile(em)
        result = await self.db.execute(stmt, params)
        rows = result.mappings().all()

        # Filter to customers with positive starting MRR
        from tidemill.metrics.mrr.cubes import MRRMovementCube

        mm = MRRMovementCube
        mq = (
            mm.dimension("customer_id") + mm.measures.amount + mm.filter("occurred_at", "<", start)
        )
        mq = mq + await build_spec_fragment(mm, narrowed, self.db)
        mstmt, mparams = mq.compile(mm)
        mresult = await self.db.execute(mstmt, mparams)
        mrr_by_cust = {
            r["customer_id"]: int(r["amount_base"] or 0) for r in mresult.mappings().all()
        }

        return [
            {
                "customer_id": r["customer_id"],
                "customer_name": r["customer_name"],
                "mrr_cents": abs(int(r["revenue_lost"] or 0)),
                "events": int(r["churn_count"]),
            }
            for r in rows
            if mrr_by_cust.get(r["customer_id"], 0) > 0
        ]
