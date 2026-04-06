"""FastAPI application with lifespan management."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response

from tidemill.bus import EventProducer
from tidemill.database import make_engine, make_session_factory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db_url = os.environ.get(
        "TIDEMILL_DATABASE_URL",
        "postgresql+asyncpg://localhost/tidemill",
    )
    kafka_url = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    engine = make_engine(db_url)

    async with engine.begin() as conn:
        from tidemill.models import metadata as sa_metadata

        await conn.run_sync(sa_metadata.create_all)

        # Ensure the "stripe" connector source exists.
        from sqlalchemy import text

        await conn.execute(
            text(
                "INSERT INTO connector_source (id, type, name, created_at)"
                " VALUES ('stripe', 'stripe', 'Stripe', NOW())"
                " ON CONFLICT (id) DO NOTHING"
            )
        )

    app.state.session_factory = make_session_factory(engine)

    producer = EventProducer(bootstrap_servers=kafka_url)
    await producer.start()
    app.state.producer = producer

    yield

    await producer.stop()
    await engine.dispose()


app = FastAPI(title="Tidemill API", lifespan=lifespan)

# Register routers
from tidemill.api.routers import health, metrics, sources, webhooks  # noqa: E402

app.include_router(health.router)
app.include_router(webhooks.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(sources.router, prefix="/api")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    # Wave emoji as SVG favicon
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        '<text y=".9em" font-size="90">📊</text></svg>'
    )
    return Response(content=svg, media_type="image/svg+xml")
