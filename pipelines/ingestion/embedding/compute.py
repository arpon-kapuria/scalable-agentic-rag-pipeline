"""
This component:
    - Runs as a Ray worker
    - Sends batches of text to an embedding API
    - Uses GPU service via HTTP
    - Adds vectors to batch data
    - Prepares chunks for vector database storage
    - Decouples CPU ingestion from GPU embedding computation
"""

import httpx
from typing import Dict, Any

class BatchEmbedder:
    """
    Callable Class for Ray Data.
    Maintains a session for efficiency.
    """
    def __init__(self):
        # Point to the internal K8s service DNS
        self.endpoint = "http://ray-serve-embed:8000/embed" # hardcode internal DNS for Ray Service
        self.client = httpx.Client(timeout=30.0)
    
    def __call__(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """
        Receives a batch of text chunks.
        Returns the batch with 'embedding' field added.
        """
        try:
            response = self.client.post(
                self.endpoint,
                json={"texts": batch["texts"], "task_type": "document"}
            )
            batch["vector"] = response.json()["embeddings"]
            return batch
        
        except Exception as e:
            # In Ray, raising exception triggers retry logic automatically
            raise e
