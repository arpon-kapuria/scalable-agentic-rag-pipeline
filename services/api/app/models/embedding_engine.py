"""
Embedding service using Ray Serve.
MINIMAL SETUP: CPU inference with float32
PRODUCTION: GPU inference with float16 and torch.compile
"""
from ray import serve
from sentence_transformers import SentenceTransformer
import os

@serve.deployment(
    num_replicas=1,
    ray_actor_options={
        "num_cpus": 1,
        "num_gpus": 0      # ← changed from 0.5, no GPU in minimal setup
    }
)
class EmbeddingDeployment:
    def __init__(self):
        model_name = os.getenv("EMBEDDING_MODEL_ID", "BAAI/bge-m3")

        # MINIMAL: CPU device
        # PRODUCTION: change "cpu" to "cuda"
        self.device = "cpu"
        self.model = SentenceTransformer(model_name, device=self.device)

        # torch.compile removed — only beneficial on GPU
        # add back in production:
        # import torch
        # self.model = torch.compile(self.model)

    async def __call__(self, request):
        body = await request.json()
        texts = body.get("text")
        task_type = body.get("task_type", "document")

        if isinstance(texts, str):
            texts = [texts]

        embeddings = self.model.encode(
            texts,
            batch_size=8,              # ← reduced from 32 for CPU
            normalize_embeddings=True
        )

        return {"embeddings": embeddings.tolist()}

app = EmbeddingDeployment.bind()