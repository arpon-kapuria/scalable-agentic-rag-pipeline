<p align="center">
  <!-- Core Language & Framework -->
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=FFD43B" alt="Python" />
  </a>
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=white" alt="uv" />
  </a>
  <a href="https://fastapi.tiangolo.com/">
    <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  </a>

  <!-- Databases -->
  <a href="https://www.postgresql.org/">
    <img src="https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  </a>
  <a href="https://redis.io/">
    <img src="https://img.shields.io/badge/Redis-FF4438?logo=redis&logoColor=white" alt="Redis" />
  </a>
  <a href="https://qdrant.tech/">
    <img src="https://img.shields.io/badge/Qdrant-DC244C?logo=qdrant&logoColor=white" alt="Qdrant" />
  </a>
  <a href="https://neo4j.com/">
    <img src="https://img.shields.io/badge/Neo4j-4581C3?logo=neo4j&logoColor=white" alt="Neo4j" />
  </a>

  <!-- Object Storage -->
  <a href="https://aws.amazon.com/s3/">
    <img src="https://img.shields.io/badge/AWS%20S3-FF9900?logo=amazons3&logoColor=white" alt="AWS S3" />
  </a>
  <a href="https://min.io/">
    <img src="https://img.shields.io/badge/MinIO-C72E49?logo=minio&logoColor=white" alt="MinIO" />
  </a>

  <!-- Distributed Compute -->
  <a href="https://www.ray.io/">
    <img src="https://img.shields.io/badge/Ray-028CF0?logo=ray&logoColor=white" alt="Ray" />
  </a>

  <!-- Infra -->
  <a href="https://www.docker.com/">
    <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker" />
  </a>
  <a href="https://kubernetes.io/">
    <img src="https://img.shields.io/badge/Kubernetes-326CE5?logo=kubernetes&logoColor=white" alt="Kubernetes" />
  </a>

  <!-- Observability -->
  <a href="https://prometheus.io/">
    <img src="https://img.shields.io/badge/Prometheus-E6522C?logo=prometheus&logoColor=white" alt="Prometheus" />
  </a>
  <a href="https://grafana.com/">
    <img src="https://img.shields.io/badge/Grafana-F46800?logo=grafana&logoColor=white" alt="Grafana" />
  </a>
</p>

---

### Structure
```
scalable-agentic-rag/
├── libs/
│   └── utils/
│       ├── backoff.py                    # retry mechanism using exponential backoff for transient failures
│       ├── document_parsing.py           # dynamic handler to parse different documents
│       ├── ids.py                        # generate unique IDs for chat sessions, files, and OpenTelemetry traces
│       └── timing.py                     # measure execution time of functions for performance monitoring
│
├── models/
│   ├── embeddings/
│   │   └── bge-m3.yaml                   # configuration for embedding model (bge-m3)
│   │
│   ├── llm/
│   │   ├── llama-7b.yaml                 # configuration for llama-3-7b-Instruct (ligher tasks)
│   │   └── llama-70b.yaml                # configuration for llama-3-70b-Instruct (heavy tasks)
│   │
│   └── rerankers/
│       └── bge-reranker.yaml             # configuration for reranker (bge-m3)
│
├── pipelines/
│   ├── ingestion/
│   │   ├── chunking/     
│   │   │   ├── metadata.py               # enrich chunk metadata and create hashes for deduplication
│   │   │   └── splitter.py               # text splitting and chunking logic
│   │   │
│   │   ├── embedding/       
│   │   │   └── compute.py                # Ray worker that batches text and generates embeddings
│   │   │
│   │   ├── graph/       
│   │   │   ├── schema.py                 # defines allowed node and relationship schema for the knowledge graph
│   │   │   └── extractor.py              # extracts entities and relationships from text using an LLM
│   │   │
│   │   ├── indexing/     
│   │   │   ├── qdrant.py                 # writes embedding vectors to the Qdrant vector database
│   │   │   └── neo4j.py                  # writes knowledge graph nodes and relationships to Neo4j
│   │   │
│   │   ├── loaders/
│   │   │   ├── docx.py                   # parses Word documents and extracts text
│   │   │   ├── html.py                   # parses HTML content and extracts clean text
│   │   │   └── pdf.py                    # parses PDF files using layout-aware extraction
│   │   │
│   │   ├── config.yaml                   # configuration for ingestion pipeline
│   │   └── main.py                       # orchestrates the distributed ingestion pipeline using Ray
│   │
│   └── jobs/
│       ├── ray_job.yaml                  # [Manual dev/testing] Ray job specification used by the Ray Job Submission API
│       └── s3_event_handler.py           # [Auto prod] Lambda handler that listens for S3 uploads and submits ingestion jobs to Ray
│
├── scripts/
│   └── bulk_upload_s3.py                 # high-performance parallel uploader to push datasets to S3
│
├── services/
│   ├── api/
│   │   ├── app/
│   │   │   ├── clients/
│   │   │   │   ├── ray_embed.py          # async client for Ray embedding service
│   │   │   │   ├── ray_llm.py            # async HTTP client to call Ray LLM service
│   │   │   │
│   │   │   ├── models/       
│   │   │   │   ├── llm_engine.py         # deploys an LLM inference service using Ray Serve and vLLM
│   │   │   │   └── embedding_engine.py   # deploys embedding service using Ray Serve and sentence_transformers
│
├── .env
├── .gitignore
├── .python-version
├── .venv
├── docker-compose.yaml
├── main.py
├── Makefile
├── pyproject.toml
├── README.md
├── uv.lock
└── workflow.md
```