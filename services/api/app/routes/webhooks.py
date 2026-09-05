"""
MinIO's webhook notification target POSTs the same S3 event-record schema
AWS uses (Records[].s3.bucket.name / .object.key), so s3_event_handler.py's
handle_s3_event() works unmodified for both — this route is just the local
HTTP receiver standing in for the Lambda trigger MinIO doesn't have.
"""
import logging
from fastapi import APIRouter, Request

from pipelines.jobs.s3_event_handler import handle_s3_event

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/minio")
async def minio_event_webhook(request: Request):
    """Receives MinIO bucket notification events, submits an ingestion job per file."""
    event = await request.json()
    logger.info(f"MinIO webhook received: {event.get('EventName', 'unknown')}")
    handle_s3_event(event, context=None)
    return {"status": "accepted"}
