"""
Single boto3 S3 client factory used by both upload.py (presigned URLs) and
the Ray ingestion pipeline (reading uploaded files). S3_ENDPOINT_URL is None
for real AWS; set to MinIO's local URL for dev/demo — everything else
(bucket, key layout, boto3 calls) stays identical either way.

Explicit Config(signature_version="s3v4", addressing_style="path") is
required for MinIO: recent boto3/botocore versions can default to
virtual-hosted-style addressing for custom endpoints, which breaks SigV4
presigned-URL signing against MinIO (manifests as SignatureDoesNotMatch on
the PUT, not at generation time — the URL looks fine, the signature just
doesn't match what MinIO recomputes). Real AWS doesn't need this forced,
but it's harmless there too, so applied unconditionally rather than
branching on S3_ENDPOINT_URL.
"""
import boto3
from botocore.config import Config
from services.api.app.config import settings


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID if settings.S3_ENDPOINT_URL else None,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY if settings.S3_ENDPOINT_URL else None,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
