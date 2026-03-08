import hashlib
import datetime

def enrich_metadata(base_metadata: dict, content: str) -> dict:
    """
    Enriches the base metadata by adding hash and timestamp for deduplication and freshness tracking.
    """
    # 1. Compute Hash (For deduplication)
    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

    # 2. Timestamp
    ingestion_time = datetime.datetime.utcnow().isoformat()

    # 3. Merge
    enriched = base_metadata.copy()
    enriched.update({
        "chunk_hash": content_hash,
        "ingested_at": ingestion_time,
        "length": len(content)
    })
    
    return enriched
    