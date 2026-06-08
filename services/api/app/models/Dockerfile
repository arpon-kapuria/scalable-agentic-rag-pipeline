# ─── Build argument to switch between minimal and production ───────────────────
# Usage:
#   Minimal (CPU):    docker build --build-arg MODE=minimal -t rag-models .
#   Production (GPU): docker build --build-arg MODE=production -t rag-models .
ARG MODE=minimal

# ─── Base image — CPU for minimal, GPU for production ─────────────────────────
FROM rayproject/ray:2.9.0-py310 AS minimal-base
FROM rayproject/ray:2.9.0-py310-gpu AS production-base

# Select base based on MODE arg
FROM ${MODE}-base AS final

WORKDIR /app

# ─── Common dependencies ───────────────────────────────────────────────────────
RUN pip install --no-cache-dir \
    sentence-transformers==2.3.1 \
    transformers==4.37.0 \
    torch==2.1.2 \
    httpx==0.26.0 \
    pydantic>=2.12.5

# ─── Production only — vLLM for GPU inference ──────────────────────────────────
RUN if [ "$MODE" = "production" ]; then \
    pip install --no-cache-dir vllm==0.3.0; \
    fi

# ─── Copy model engine files ───────────────────────────────────────────────────
COPY services/api/app/models/ .
COPY libs/ /app/libs/

ENV PYTHONPATH=/app

# Ray Serve manages startup via import_path — no CMD needed