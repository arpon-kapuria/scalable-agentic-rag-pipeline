# Workflow

- [ ] Missing packages - vllm, PyTorch, redis, sqlalchemy, langgraph, simpleeval, Tavily api key in .env, lua, nginx


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
- [x] Implement query enhancement in `services/api/app/enhancers/` using *HyDE* for improved retrieval accuracy and coreference resolution to rewrite ambiguous queries into standalone search queries before hitting the retriever.
- [x] Implement the FastAPI application entrypoint in `services/api/main.py` managing lifecycle events — initializing database connections on startup and closing them gracefully on shutdown.

> **Why JSON logging over Standard text logging?**
> Standard text logs are useless at scale when you have 50 pods running. JSON logs allow us to query logs like a database, filtering by error levels or specific request IDs to trace bugs across distributed nodes.


### Tools & Sandbox
- [x] Implement a hardened sandbox microservice in `services/sandbox/` — a isolated Docker container running a Flask execution server with a non-root user, CPU/RAM resource limits, and a Kubernetes NetworkPolicy blocking all egress traffic, ensuring LLM-generated code cannot exfiltrate data or affect the host system.
- [x] Implement an isolated sandbox client in `services/api/app/tools/sandbox.py` that sends LLM-generated code to the sandbox over HTTP.
- [x] Implement safe deterministic tools in `services/api/app/tools/` — a math expression evaluator using AST parsing (`calculator.py`), an entity-aware Neo4j search with two-stage Cypher injection prevention (`graph_search.py`), a Qdrant document retrieval tool (`vector_search.py`), a real-time web search via Tavily API (`web_search.py`).
- [x] Implement the main chat route in `services/api/app/routes/chat.py` — orchestrating the full RAG pipeline with semantic cache fast path, conversation history loading, LangGraph agent streaming, and post-processing memory and cache updates via NDJSON streaming response.
- [x] Implement supporting API routes — presigned S3 URL generation for large file uploads in `routes/upload.py`, RLHF feedback collection in `routes/feedback.py`, and Kubernetes liveness/readiness health checks in `routes/health.py`.
- [x] Implement gateway rate limiting in `services/gateway/rate_limit.lua` using a *token bucket algorithm* in Nginx/OpenResty with Redis as the counter backend — blocking excessive traffic before it reaches FastAPI.
- [x] We have now built the entire application stack: Ingestion, Models, Agent, and Tools. 


### Infrastructure as Code (IaC)
- [x] We use **Terraform** to define our entire cloud footprint as code. This allows us to spin up identical dev, staging, and prod environments in minutes. We also use **Karpenter** for intelligent, just-in-time node scaling that is faster and cheaper than standard AWS Auto Scaling Groups.
- [x] Set up Terraform foundation with remote state — configure AWS, Kubernetes and Helm providers in `infra/terraform/main.tf`, store the state file in S3 with DynamoDB locking so two engineers can never corrupt the infrastructure by running terraform apply at the same time.
- [x] Parameterize the entire infrastructure in `infra/terraform/variables.tf` — define region, environment, cluster name and database password as variables so the same Terraform code deploys identical dev, staging and prod environments by just swapping a .tfvars file.
- [x] Build a 3-tier VPC in `infra/terraform/vpc.tf` — public subnets for load balancers, private subnets for application pods, database subnets for PostgreSQL and Redis, all spread across 3 availability zones so a single data center failure doesn't take down the platform. NAT Gateways allow pods to download packages without being exposed to the internet
- [x] Provision the EKS Kubernetes cluster in `infra/terraform/eks.tf` — deploy a small always-on system node group just for CoreDNS and Karpenter, enable OIDC so individual pods can authenticate to AWS using short-lived tokens instead of hardcoded credentials.
- [x] Lock down AWS permissions in `infra/terraform/iam.tf` — give the Ray ingestion worker access to the documents S3 bucket and nothing else, so a compromised pod cannot touch databases, billing or any other AWS resource.
- [x] Provision all managed databases — Aurora Serverless PostgreSQL that automatically scales compute from cheap to powerful based on chat traffic in `infra/terraform/rds.tf`, encrypted Redis with a hot-standby replica in `infra/terraform/redis.tf`, versioned S3 bucket with Transfer Acceleration for fast global uploads and automatic cost-saving storage tiering after 30 days in `infra/terraform/s3.tf`, and a firewall rule blocking all external internet access to Neo4j in `infra/terraform/neo4j.tf`.
- [x] Export every database endpoint and cluster URL in `infra/terraform/outputs.tf` so they can be directly plugged into Kubernetes secrets in the next step.
- [x] Configure Karpenter autoscaling with a CPU provisioner in `infra/karpenter/provisioner-cpu.yaml` using Spot instances with consolidation for stateless API pods, and a GPU provisioner in `infra/karpenter/provisioner-gpu.yaml` with TTL-based scale-to-zero for Ray LLM inference nodes — paying for GPUs only during active inference.


### Deployment
- [ ] 