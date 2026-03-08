import os
import uuid
from typing import Any, Dict, List
from qdrant_client import QdrantClient
from qdrant_client.http import models


class QdrantIndexer:
    """
    Writes embedding vectors into the Qdrant vector database
    """
    def __init__(self):
        host = os.getenv("QDRANT_HOST", "qdrant-service")   # qdrant-service = internal K8s DNS
        port = int(os.getenv("QDRANT_PORT", 6333))
        self.collection_name = os.getenv("QDRANT_COLLECTION", "scalable_rag_collection")

        self.client = QdrantClient(host=host, port=port)
        
    def write(self, batch: List[Dict[str, Any]]):
        """
        Uploads points in batch.
        """
        points = []

        for row in batch:
            # Skip if embedding failed
            if "vector" not in row:
                continue

            # Construct Payload (Metadata)
            payload = {
                "text": row["text"],
                "filename": row["metadata"]["filename"],
                "page": row["metadata"].get("page_number", 0)
            }

            # Create Point
            points.append(
                models.PointStruct(
                    id = str(uuid.uuid4()), # Generate unique ID for the vector
                    vector = row["vector"],
                    payload = payload
                )
            )

        if points:
            # Upsert is atomic
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )