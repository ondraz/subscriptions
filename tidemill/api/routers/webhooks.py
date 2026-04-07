"""Generic webhook endpoint for connectors without custom routes."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/{source_type}")
async def receive_webhook(
    source_type: str,
    request: Request,
) -> Response:
    from tidemill.api.app import app
    from tidemill.connectors import get_connector

    body = await request.body()
    payload = await request.json()

    source_id = request.query_params.get("source_id", source_type)
    config = getattr(app.state, "connector_configs", {}).get(source_type, {})

    connector = get_connector(source_type, source_id=source_id, config=config)

    sig = request.headers.get("x-webhook-signature", "")
    if sig and not connector.verify_signature(body, sig):
        return Response(status_code=400, content="Invalid signature")

    events = connector.translate(payload)
    if events:
        producer = app.state.producer
        await producer.publish_many(events)

    return Response(status_code=200, content="ok")
