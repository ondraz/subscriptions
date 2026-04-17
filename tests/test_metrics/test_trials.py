"""Tests for TrialsMetric.handle_event — SQLite in-memory."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tidemill.metrics.trials.metric import TrialsMetric

from .conftest import T0, T1, T2, make_evt


class TestTrialsHandler:
    @pytest.fixture
    def metric(self, db) -> TrialsMetric:
        m = TrialsMetric()
        m.init(db=db)
        return m

    @pytest.mark.asyncio
    async def test_trial_started(self, metric, db):
        event = make_evt(
            "subscription.trial_started",
            {"external_id": "sub_1", "trial_start": "2026-01-15", "trial_end": "2026-02-14"},
        )
        await metric.handle_event(event)
        await db.commit()

        row = (
            await db.execute(
                text(
                    "SELECT event_type, subscription_id, customer_id"
                    " FROM metric_trial_event WHERE subscription_id = 'sub_1'"
                )
            )
        ).fetchone()
        assert row is not None
        assert row[0] == "started"
        assert row[1] == "sub_1"
        assert row[2] == "cus_1"

    @pytest.mark.asyncio
    async def test_trial_converted(self, metric, db):
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_converted",
                {"external_id": "sub_1", "mrr_cents": 7900},
                occurred_at=T1,
                external_id="sub_1:converted",
            )
        )
        await db.commit()

        rows = (
            await db.execute(
                text(
                    "SELECT event_type FROM metric_trial_event"
                    " WHERE subscription_id = 'sub_1'"
                    " ORDER BY occurred_at"
                )
            )
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "started"
        assert rows[1][0] == "converted"

    @pytest.mark.asyncio
    async def test_trial_expired(self, metric, db):
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_expired",
                {"external_id": "sub_1"},
                occurred_at=T1,
                external_id="sub_1:expired",
            )
        )
        await db.commit()

        rows = (
            await db.execute(
                text(
                    "SELECT event_type FROM metric_trial_event"
                    " WHERE subscription_id = 'sub_1'"
                    " ORDER BY occurred_at"
                )
            )
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "started"
        assert rows[1][0] == "expired"

    @pytest.mark.asyncio
    async def test_idempotent_replay(self, metric, db):
        """Processing the same event twice → one row."""
        event = make_evt(
            "subscription.trial_started",
            {"external_id": "sub_1"},
        )
        await metric.handle_event(event)
        await db.commit()
        await metric.handle_event(event)
        await db.commit()

        count = (await db.execute(text("SELECT COUNT(*) FROM metric_trial_event"))).scalar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_multiple_trials(self, metric, db):
        """Different subscriptions create separate trial events."""
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_2"},
                customer_id="cus_2",
                external_id="sub_2",
                occurred_at=T1,
            )
        )
        await db.commit()

        count = (await db.execute(text("SELECT COUNT(*) FROM metric_trial_event"))).scalar()
        assert count == 2

    @pytest.mark.asyncio
    async def test_started_populates_metric_trial(self, metric, db):
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,
            )
        )
        await db.commit()

        row = (
            await db.execute(
                text(
                    "SELECT subscription_id, started_at, converted_at, expired_at"
                    " FROM metric_trial WHERE subscription_id = 'sub_1'"
                )
            )
        ).fetchone()
        assert row is not None
        assert row[0] == "sub_1"
        assert row[1] is not None
        assert row[2] is None
        assert row[3] is None

    @pytest.mark.asyncio
    async def test_converted_sets_converted_at(self, metric, db):
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_converted",
                {"external_id": "sub_1"},
                occurred_at=T1,
                external_id="sub_1:converted",
            )
        )
        await db.commit()

        row = (
            await db.execute(
                text(
                    "SELECT started_at, converted_at, expired_at"
                    " FROM metric_trial WHERE subscription_id = 'sub_1'"
                )
            )
        ).fetchone()
        assert row[0] is not None  # started_at
        assert row[1] is not None  # converted_at
        assert row[2] is None  # expired_at

    @pytest.mark.asyncio
    async def test_out_of_order_converted_before_started(self, metric, db):
        """Converted arriving before started still produces a well-formed row.

        The later started event corrects started_at via LEAST(...).
        """
        await metric.handle_event(
            make_evt(
                "subscription.trial_converted",
                {"external_id": "sub_1"},
                occurred_at=T1,
                external_id="sub_1:converted",
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,
            )
        )
        await db.commit()

        row = (
            await db.execute(
                text(
                    "SELECT started_at, converted_at"
                    " FROM metric_trial WHERE subscription_id = 'sub_1'"
                )
            )
        ).fetchone()
        assert row[0] is not None
        assert row[1] is not None

    @pytest.mark.asyncio
    async def test_cohort_funnel_attributes_late_conversion_to_start_period(self, metric, db):
        """A trial started in Jan that converts in Feb counts toward Jan."""
        from datetime import date

        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,  # Jan 15
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_converted",
                {"external_id": "sub_1"},
                occurred_at=T1,  # Feb 15
                external_id="sub_1:converted",
            )
        )
        await db.commit()

        # Query: January-only window — conversion in February should still
        # count because the cohort is defined by started_at.
        funnel = await metric._funnel(date(2026, 1, 1), date(2026, 2, 1), None)
        assert funnel["started"] == 1
        assert funnel["converted"] == 1
        assert funnel["conversion_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_cohort_funnel_excludes_prior_cohort_conversion(self, metric, db):
        """Trials started before the window don't count, even if they convert inside.

        Cohort attribution is fixed by started_at, not converted_at.
        """
        from datetime import date

        await metric.handle_event(
            make_evt(
                "subscription.trial_started",
                {"external_id": "sub_1"},
                occurred_at=T0,  # Jan 15 — outside the Feb window
            )
        )
        await metric.handle_event(
            make_evt(
                "subscription.trial_converted",
                {"external_id": "sub_1"},
                occurred_at=T1,  # Feb 15 — inside
                external_id="sub_1:converted",
            )
        )
        await db.commit()

        funnel = await metric._funnel(date(2026, 2, 1), date(2026, 3, 1), None)
        assert funnel["started"] == 0
        assert funnel["converted"] == 0
        assert funnel["conversion_rate"] is None

    @pytest.mark.asyncio
    async def test_full_funnel(self, metric, db):
        """Full trial funnel: 3 started, 2 converted, 1 expired."""
        for i in range(3):
            await metric.handle_event(
                make_evt(
                    "subscription.trial_started",
                    {"external_id": f"sub_{i}"},
                    customer_id=f"cus_{i}",
                    external_id=f"sub_{i}",
                    occurred_at=T0,
                )
            )

        for i in range(2):
            await metric.handle_event(
                make_evt(
                    "subscription.trial_converted",
                    {"external_id": f"sub_{i}", "mrr_cents": 7900},
                    customer_id=f"cus_{i}",
                    external_id=f"sub_{i}:converted",
                    occurred_at=T1,
                )
            )

        await metric.handle_event(
            make_evt(
                "subscription.trial_expired",
                {"external_id": "sub_2"},
                customer_id="cus_2",
                external_id="sub_2:expired",
                occurred_at=T2,
            )
        )
        await db.commit()

        rows = (
            await db.execute(
                text(
                    "SELECT event_type, COUNT(*) as cnt FROM metric_trial_event"
                    " GROUP BY event_type ORDER BY event_type"
                )
            )
        ).fetchall()
        by_type = {r[0]: r[1] for r in rows}
        assert by_type["started"] == 3
        assert by_type["converted"] == 2
        assert by_type["expired"] == 1
