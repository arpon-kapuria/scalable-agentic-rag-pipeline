import logging
from urllib.parse import unquote_plus
from ray.job_submission import JobSubmissionClient
from services.api.app.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handle_s3_event(event: dict, context=None):
    """
    Entry point for an S3-event-shaped payload — called by the MinIO webhook
    route locally, or (unmodified) by a real Lambda trigger against AWS S3
    in a later deploy. `context` is unused here; kept for Lambda-signature
    compatibility so the same function works in both call sites.
    """
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])

        logger.info(f"File uploaded: s3://{bucket}/{key}")
        submit_ingestion_job(bucket, key)


def submit_ingestion_job(bucket: str, file_key: str):
    """
    Submits a job to the Ray cluster via the Job Submission REST API — the
    driver script parses corpus_id from the key (uploads/{corpus_id}/...)
    and does the actual parse/chunk/embed/index work as a background job,
    not inline in this (fast) event handler.
    """
    client = JobSubmissionClient(settings.RAY_ADDRESS)

    try:
        job_id = client.submit_job(
            entrypoint=f"python pipelines/ingestion/main.py {bucket} {file_key}",
            # Local ray-worker image has ingestion+ray uv groups pre-installed
            # (see deploy/ray/Dockerfile.local) — no pip runtime_env needed.
            runtime_env={
                "working_dir": "./",
                # This function runs inside the FastAPI process (host,
                # `uv run uvicorn ... --env-file .env`) — JobSubmissionClient
                # inherits *that* process's env into the job's runtime_env,
                # which then overrides the ray-worker container's own
                # docker-compose environment: block for the actual job run.
                # Host .env has host-perspective values (localhost:7687 etc,
                # since Neo4j/Qdrant/MinIO ports are published to the host
                # for the API's own use) — wrong for a job running inside
                # the Docker network. Force the container-network values
                # explicitly here; job-level runtime_env has the highest
                # precedence, so this can't be silently overridden again.
                "env_vars": {
                    "QDRANT_HOST": "qdrant",
                    "NEO4J_URI": "bolt://neo4j:7687",
                    "S3_ENDPOINT_URL": "http://minio:9000",
                    "REDIS_URL": "redis://redis:6379/0",
                },
            },
        )
        logger.info(f"Submitted Ray Job ID: {job_id}")
        return job_id
    except Exception as e:
        logger.error(f"Ray job submission failed: {e}")
        raise
