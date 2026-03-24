# Workflow

- [ ] Missing packages - vllm, PyTorch, redis, sqlalchemy, langgraph


### Dataset Preparation:
- [ ] Collect 950 random pdfs from this repo [https://github.com/tpn/pdfs.git] and put them into `noisy_data` folder
- [ ] Using a script, scrape open-source kubernetes official documentation and saved them in different formats such as pdf, docx, txt, html files in the `true_data` directory
- [ ] Merge both noisy and true data into a single `data` directory


### Data Storage Setup
- [ ] `Aurora Postgres` for chat history and metadata storage
- [ ] `Redis` for caching frequently accessed data
- [ ] `Qdrant` as our vector database for storing embeddings
- [ ] `Neo4j` as our graph database for storing relationships between entities
- [ ] `AWS S3` as our primary document storage along with clustered Ray serving for hosting our AI models (LLM, Embeddings, Rerankers)
- [ ] `MinIO` works as fake AWS S3 for local development


### Setup Development Workflow
- [x] `.env` file to share environment variables required for local development.
- [x] `Makefile` to automate common tasks such as building, testing and deploying the application
- [x] `docker-compose.yaml` file to define all the services required to run the entire rag pipeline locally using Docker containers
- [x] Create shared utilies files `(ids.py, timing.py, backoff.py, document_parsing.py)`

> `docker-compose.yaml` file pulls and runs the 5 services `(pgsql, redis, qdrant, neo4j, minio)` and uv runs the fastapi app. It simulates everything locally. No need to install those services.


### Data Ingestion Layer
- [x] Setup Ray Data to distribute data ingestion process so that tasks can be processed parallely (creates DAG of taks)
- [x] Create separate loader files `(pdf.py, docx.py, html.py)`, where we use temporary files to handle memory efficiently
- [x] Split the raw text using `splitter.py` text into 512-token chunks (standard limit for many embedding models)
- [x] Enrich the chunk's base metadata by adding hash and timestamp for deduplication and freshness tracking in  `metadata.py`
- [x] Batch processing of text chunks to generate vector embeddings using Ray worker (GPU embedding service) in `compute.py`
- [x] Extract knowledge-graph relationships using `extractor.py` from the text chunks following the schema defined in `schema.py` file
- [x] Index embeddings into vector database `qdrant.py` for semantic vector search 
- [x] Index knowledge-graph nodes and relationships into graph database `neo4j.py` for entity relationship reasoning
- [x] Combine all the ingestion components in one file `ingestion/main.py` to process parallely
- [x] Setup `ray_job.yaml` as a manual trigger for Ray distributed ingestion pipeline during development and testing
- [x] Setup `s3_event_handler.py` as the production event-driven trigger — automatically submits an ingestion job to Ray when a file is uploaded to S3
- [x] The `pipelines/jobs/requirements-ray.txt` file needs to be generated using `Makefile` command from our main pyproject.toml but only includes the dependencies needed for the ingestion job (not the entire platform)
- [x] Setup `bulk_upload_s3.py` script that scans a local directory and uploads all files to S3 in parallel using multipart upload with retries, automatically triggering the downstream ingestion pipeline via S3 events


### AI Compute Layer
- [x] Setup Ray Serve to host models as independent microservices that can auto scale based on GPU availability and traffic
- [x] Keep separate model configuration files for chat models `(llama-7b, llama-70b)`, embedding models `(bge-m3)` and reranker `(bge-reranker)` in `models` folder and deployment services in `services/api/app/models/` folder
- [x] Serve AI models with `vLLM` and embedding models & rerankers with `sentence_transformers`
- [x] Implement async HTTP clients used by the API server to communicate with the Ray-Serve LLM `ray_llm.py` & Embedding service `ray_embed.py`

> **Why vLLM instead of HuggingFace pipelines?**
> - **Higher throughput** – optimized for serving many concurrent requests.
> - **PagedAttention** – prevents GPU memory fragmentation in KV cache.
> - **Dynamic batching** – processes tokens from multiple requests together.
> - **Better GPU utilization** – supports far more simultaneous generations.
> - **Lower latency under load** – designed for production inference, not experimentation.


### Agentic AI Layer
- [x] Setup `services/api/requirements.txt` file, which ensures we have all the asynchronous drivers (asyncpg, redis) and observability tools (opentelemetry) needed for a high-performance system.
- [x] Create `services/api/app/config.py` using Pydantic Settings. This validates that all our database URLs and API keys exist at startup, preventing runtime crashes later
- [x] Implement structured JSON logging `services/api/app/logging.py` to make logs machine-readable for tools like Datadog or Splunk.
- [x] Enable distributed tracing in `services/api/app/observability.py`. This tracks a request flow from the API to Redis, then to the Vector DB, and finally to the Ray Cluster. 
- [x] Implement JWT (JSON Web Token) validation in `services/api/app/auth/jwt.py`. This middleware make sure that only authorized users can query our expensive GPU resources.
- [x] Define the data schemas in `libs/schemas/chat.py`. This ensures the frontend sends exactly what we expect and receives a consistent response structure.
- [x] Implement a singleton Redis connection manager in `services/api/app/cache/redis.py` for cache and rate limiting. It prevents *"Too many connections"* error.
- [x] Implement an async Qdrant client in `services/api/app/clients/qdrant.py` and an async Neo4j client in `services/api/app/clients/neo4j.py`, both managing connection pools for non-blocking vector search and Cypher-based graph traversal respectively.
- [x] Define the SQLAlchemy ORM schema in `services/api/app/memory/models.py` to model the chat_history table for persisting the full conversation history to PostgreSQL.
- [x] Implement the CRUD logic in `services/api/app/memory/postgres.py`. We fetch the history in reverse chronological order to feed the most recent context to the LLM.
- [x] To lower the latency and reduce llm calls, implement sementic cache using Qdrant vector similarity in `services/api/app/cache/semantic.py`. If a user asks "What is Kubernetes?" and another asks "Explain K8s", the embedding similarity will be high.
- [x] Implement the LangGraph agent pipeline in `services/api/app/agents/` — comprising a **planner** node that rewrites the query and routes to retrieval, direct answer, or tool use; a **retriever** node that runs Qdrant vector search and Neo4j graph traversal concurrently; a **responder** node that synthesizes the final answer with source citations; and a **tool** node for calculator and graph search execution — all wired together in `graph.py` with conditional routing based on planner decisions.


> **Why JSON logging over Standard text logging?**
> Standard text logs are useless at scale when you have 50 pods running. JSON logs allow us to query logs like a database, filtering by error levels or specific request IDs to trace bugs across distributed nodes.