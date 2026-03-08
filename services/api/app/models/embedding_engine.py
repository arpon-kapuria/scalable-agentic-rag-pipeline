"""
This file creates a GPU-backed embedding service using Ray Serve.
Its job is to convert text into vector embeddings that will later be stored in a vector database like Qdrant.
"""

from ray import serve
from sentence_transformers import SentenceTransformer
import torch
import os

@serve.deployment(num_replicas=1, ray_actor_options={"num_gpus": 0.5})
class EmbeddingDeployment:
    def __init__(self):
        model_name = "BAAI/bge-m3"
        self.model = SentenceTransformer(model_name, device="cuda")

        # Compile for speed (Optional, requires PyTorch 2.0+)
        self.model = torch.compile(self.model)

    async def __call__(self, request):
        body = await request.json()
        texts = body.get("text")
        task_type = body.get("task_type", "document")

        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True   # improves cosine similarity search
        )

        return {"embeddings": embeddings.to_list()}

app = EmbeddingDeployment.bind()