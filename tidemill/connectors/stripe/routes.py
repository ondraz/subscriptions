"""Stripe webhook endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/stripe")
async def receive_stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None),
) -> Response:
    from tidemill.api.app import app
    from tidemill.connectors import get_connector

    body = await request.body()
    payload = await request.json()

    source_id = request.query_params.get("source_id", "stripe")
    config = getattr(app.state, "connector_configs", {}).get("stripe", {})

    connector = get_connector("stripe", source_id=source_id, config=config)

    if stripe_signature and not connector.verify_signature(body, stripe_signature):
        return Response(status_code=400, content="Invalid signature")

    events = connector.translate(payload)
    if events:
        producer = app.state.producer
        await producer.publish_many(events)

    return Response(status_code=200, content="ok")
