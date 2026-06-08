### Phase 1 — One-time Manual Setup (AWS Console)

``` bash
AWS Console
    ↓
Create S3 bucket: scalable-rag-platform-terraform-state-dev-001
    - Enable versioning
    - Enable SSE-S3 encryption
    - Block all public access
    ↓
Create DynamoDB table: terraform-state-lock
    - Partition key: LockID (String)
    - On-demand capacity
    ↓
Create IAM user: macbook-air-cli
    - Attach AdministratorAccess policy
    - Generate Access Key + Secret Key
    ↓
aws configure
    - paste Access Key, Secret Key
    - region: us-east-1
    - format: json
```

Terraform needs somewhere to store its state file before it can create anything. 


### Phase 2 — Infrastructure Provisioning

``` bash
make infra
# runs: cd infra/terraform && terraform init && terraform apply
```

``` bash
> terraform init

reads main.tf backend config
    ↓
connects to S3 bucket (state storage)
    ↓
acquires DynamoDB lock (prevents concurrent applies)
    ↓
downloads providers:
    hashicorp/aws      → talks to AWS APIs
    hashicorp/kubernetes → talks to K8s APIs
    hashicorp/helm     → manages Helm releases
    ↓
downloads modules:
    terraform-aws-modules/vpc
    terraform-aws-modules/eks
    terraform-aws-modules/rds-aurora (or RDS)
    terraform-aws-modules/iam
```

``` bash
> terraform apply 

# creates around 38-48 resources in order:
vpc.tf
    → VPC (10.0.0.0/16) — your private network
    → 2 public subnets  — load balancers, NAT gateways
    → 2 private subnets — EKS nodes, application pods
    → 2 database subnets — RDS, Redis
    → 1 NAT Gateway — allows private pods to reach internet
    → Internet Gateway — allows public subnets to reach internet
    → Route tables — network routing rules
    ↓
eks.tf
    → EKS control plane — Kubernetes master (managed by AWS)
    → OIDC provider — enables pod-level AWS identity (IRSA)
    → System node group — 1x t3.medium EC2 instance
        runs: CoreDNS, kube-proxy, aws-node
    ↓
iam.tf
    → IAM policy — S3 read/write for Ray workers only
    → IRSA role — binds policy to ray-worker service account
    → Trust relationship — only ray-worker pod in default namespace
    ↓
rds.tf
    → RDS subnet group — which subnets DB lives in
    → RDS security group — only port 5432 from VPC
    → RDS PostgreSQL t3.micro — stores chat history, feedback
    ↓
redis.tf
    → ElastiCache subnet group
    → Redis security group — only port 6379 from VPC
    → ElastiCache t3.micro — semantic cache, rate limiting
    ↓
s3.tf
    → S3 bucket — document storage
    → Versioning — accidental overwrites recoverable
    → CORS rules — allows browser presigned URL uploads
    ↓
neo4j.tf
    → Security group — ports 7687 (Bolt) and 7474 (HTTP)
    → VPC-only access — internet cannot reach Neo4j
    ↓
ecr.tf
    → ECR repository: rag-api — stores your API Docker image
    → ECR repository: rag-models — stores Ray model image
    → Lifecycle policy — keeps last 5 images, auto-deletes old
    ↓
outputs.tf
    → prints all endpoints:
        eks_cluster_name
        eks_cluster_endpoint
        postgres_db_endpoint
        redis_endpoint
        s3_documents_bucket_name
        ecr_api_url
        ecr_models_url
```

State saved to S3, DynamoDB lock released.


### Phase 3 — Store Secrets in AWS Secrets Manager

``` bash
# manual step after terraform output
aws secretsmanager create-secret \
    --name prod/rag/db_creds \
    --secret-string '{
        "DATABASE_URL": "postgresql+asyncpg://ragadmin:pass@<postgres_endpoint>:5432/ragdb",
        "REDIS_URL": "redis://<redis_endpoint>:6379/0",
        "NEO4J_PASSWORD": "yourpassword",
        "JWT_SECRET_KEY": "yoursecret"
    }'

aws secretsmanager create-secret \
    --name prod/rag/api_keys \
    --secret-string '{
        "openai_api_key": "sk-...",
        "tavily_api_key": "tvly-..."
    }'
```

Your app needs database passwords but they can never be in code or Docker images. AWS Secrets Manager is the secure vault — External Secrets Operator will fetch them later.


### Phase 4 — Build and Push Docker Images

``` bash
make docker
# runs: docker-login → docker-build → docker-tag → docker-push
```

``` bash
> docker-login

aws ecr get-login-password
    ↓
authenticates Docker CLI with ECR
    ↓
Docker can now push to your private registry
```

``` bash
> docker-build

services/api/Dockerfile
    FROM python:3.13-slim
        ↓
    apt-get install gcc g++ curl libpq-dev
        ↓
    pip install -r requirements.txt
    (fastapi, uvicorn, sqlalchemy, asyncpg, redis,
     neo4j, qdrant-client, langchain, langgraph,
     opentelemetry, boto3, httpx, pyjwt...)
        ↓
    COPY . /app
    (copies all your Python code)
        ↓
    ENV PYTHONPATH=/app
        ↓
    CMD uvicorn services.api.main:app --port 8000
    ↓
Image: rag-api (contains your entire API)

services/api/app/models/Dockerfile
    FROM rayproject/ray:2.9.0-py310
        ↓
    pip install sentence-transformers transformers torch httpx
        ↓
    COPY embedding_engine.py llm_engine.py
        ↓
Image: rag-models (contains Ray model serving code)
```

``` bash
> docker-tag and docker-push

tag images with ECR URL:
    371637912340.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
    371637912340.dkr.ecr.us-east-1.amazonaws.com/rag-models:latest
        ↓
push to ECR
        ↓
images stored securely in AWS — accessible by EKS only
```


### Phase 5 — Bootstrap the Cluster

``` bash
make bootstrap
# runs: ./scripts/bootstrap_cluster.sh
```

**Step 1 — Connect kubectl to EKS**

``` bash
aws eks update-kubeconfig --name rag-platform-cluster
    ↓
writes cluster credentials to ~/.kube/config
    ↓
kubectl now talks to your EKS cluster
    ↓
all subsequent kubectl/helm commands hit your cluster
```

**Step 2 — Install KubeRay Operator**

``` bash
helm install kuberay-operator kuberay/kuberay-operator
    ↓
runs as pod in cluster
    ↓
watches for RayCluster and RayService resources
    ↓
manages Ray cluster lifecycle automatically
```

**Step 3 — Install External Secrets Operator**

``` bash
helm install external-secrets external-secrets/external-secrets
    ↓
runs as pod in cluster
    ↓
watches for ExternalSecret resources
    ↓
connects to AWS Secrets Manager via IRSA
```

**Step 4 — Install Nginx Ingress Controller**

``` bash
helm install ingress-nginx ingress-nginx/ingress-nginx
    ↓
creates AWS Load Balancer automatically
    ↓
all HTTP traffic enters cluster through this
    ↓
routes to correct internal service based on path
```

**Step 5 — Apply External Secrets**

``` bash
kubectl apply -f deploy/secrets/external-secrets.yaml
    ↓
External Secrets Operator reads the resource
    ↓
calls AWS Secrets Manager:
    prod/rag/db_creds  → DATABASE_URL, REDIS_URL,
                         NEO4J_PASSWORD, JWT_SECRET_KEY
    prod/rag/api_keys  → OPENAI_API_KEY, TAVILY_API_KEY
    ↓
creates Kubernetes Secret: "app-env-secret"
    ↓
refreshes every 1 hour automatically
```

**Step 6 — Deploy Qdrant**

``` bash
helm install qdrant deploy/helm/qdrant -f deploy/helm/qdrant/values.yaml
    ↓
reads qdrant/values.yaml:
    replicaCount: 1
    memory: 1Gi
    storage: 10Gi gp2 SSD
    on_disk_payload: true
    ↓
creates Qdrant pod + PersistentVolumeClaim (EBS volume)
    ↓
Qdrant starts, collections created on first API startup
    ↓
accessible internally as: qdrant-service:6333
```

**Step 7 — Deploy Ray Cluster**

``` bash
kubectl apply -f deploy/ray/ray-cluster.yaml
    ↓
KubeRay operator reads RayCluster spec
    ↓
creates Ray Head pod:
    image: rayproject/ray:2.9.0-py310
    cpu: 1, memory: 2Gi
    num-cpus: 0 (head never runs tasks)
    ports: 6379 (internal Redis), 8265 (dashboard)
    ↓
creates CPU Worker pod:
    image: rayproject/ray:2.9.0-py310
    cpu: 1, memory: 2Gi
    runs actual computation tasks
    ↓
Ray cluster forms — workers register with head
    ↓
sleep 30 — wait for cluster to stabilize
```

**Step 8 — Deploy AI Model Services**

``` bash
kubectl apply -f deploy/ray/ray-serve-embed.yaml
    ↓
KubeRay reads RayService spec
    ↓
Ray Serve loads:
    import_path: services.api.app.models.embedding_engine:app
    ↓
EmbeddingDeployment.__init__() runs:
    loads BAAI/bge-m3 model (downloads ~500MB)
    device: cpu
    ↓
exposes endpoint: /embed internally
    ↓
accessible as: http://embed-service:8000/embed

kubectl apply -f deploy/ray/ray-serve-llm.yaml
    ↓
Ray Serve loads:
    import_path: services.api.app.models.llm_engine:app
    env: MODEL_ID=TinyLlama/TinyLlama-1.1B-Chat-v1.0
    ↓
VLLMDeployment.__init__() runs:
    loads TinyLlama model (downloads ~2GB)
    device: cpu, dtype: float32
    ↓
exposes endpoint: /llm internally
    ↓
accessible as: http://llm-service:8000/llm
```

**Step 9 — Deploy Nginx Ingress Rules**

``` bash
kubectl apply -f deploy/ingress/nginx.yaml
    ↓
Ingress resource tells Nginx controller:
    api.your-rag-platform.com/chat   → api-service:80
    api.your-rag-platform.com/upload → api-service:80
    proxy-read-timeout: 3600s (for LLM streaming)
```

**Step 10 — Deploy API**

``` bash
helm install api deploy/helm/api
    ↓
Helm reads Chart.yaml (validates chart)
    ↓
Helm reads values.yaml:
    image: 371637912340.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
    env vars: QDRANT_HOST, NEO4J_URI, RAY_LLM_ENDPOINT...
    envFromSecret: app-env-secret
    ↓
renders templates/deployment.yaml:
    creates Deployment resource
    Kubernetes pulls rag-api image from ECR
    injects env vars from values.yaml
    injects secrets from app-env-secret:
        DATABASE_URL, REDIS_URL, NEO4J_PASSWORD, JWT_SECRET_KEY
    ↓
renders templates/service.yaml:
    creates Service: api-service:80 → pod:8000
    ↓
API pod starts:
    uvicorn starts on port 8000
    lifespan() runs:
        create_all() → creates chat_history, feedback tables in RDS
        neo4j_client.connect() → connects to Neo4j pod
        redis_client.connect() → connects to ElastiCache
        llm_client.start() → opens httpx connection pool to /llm
        embed_client.start() → opens httpx connection pool to /embed
        qdrant_client.init_collections() → creates vector collections
    ↓
health checks pass:
    GET /health/liveness → 200 OK
    GET /health/readiness → Redis up, Neo4j up → 200 OK
    ↓
pod marked Ready
    ↓
Nginx starts routing traffic to it
```


### Phase 6 — Upload Documents and Trigger Ingestion

``` bash
python scripts/bulk_upload_s3.py ./data rag-platform-documents-dev-001
    ↓
ThreadPoolExecutor — 10 parallel uploads
    ↓
boto3 multipart upload for files >25MB
    ↓
files land in S3: uploads/user-id/file-uuid.pdf
    ↓
S3 event triggers s3_event_handler.py
    ↓
JobSubmissionClient.submit_job()
    ↓
Ray Head receives job
    ↓
pipelines/ingestion/main.py runs on Ray cluster:

    ray.data.read_binary_files(s3://bucket/prefix)
        ↓ lazy load
    ds.map_batches(process_batch, num_cpus=1)
        ↓ per file:
        document_parsing.py::parse_document()
            → pdf.py::parse_pdf_bytes()     (unstructured OCR)
            → docx.py::parse_docx_bytes()   (python-docx)
            → html.py::parse_html_bytes()   (BeautifulSoup)
        splitter.py::split_text()
            → RecursiveCharacterTextSplitter (512 tokens, 50 overlap)
        metadata.py::enrich_metadata()
            → adds MD5 hash, timestamp, chunk_index
        ↓
    FORK — two parallel branches:

    Branch A — Embeddings:
        ds.map_batches(BatchEmbedder, num_cpus=1)
            ↓
        HTTP POST to embed-service:8000/embed
            ↓
        EmbeddingDeployment.__call__()
            SentenceTransformer.encode(texts)
            returns 768-dim vectors
            ↓
        batch["vector"] = embeddings
            ↓
        QdrantIndexer.write(batch)
            qdrant_client.upsert(collection, points)
            → vectors + metadata stored in Qdrant

    Branch B — Graph Extraction:
        ds.map_batches(GraphExtractor, num_cpus=1)
            ↓
        HTTP POST to llm-service:8000/llm
            ↓
        VLLMDeployment.__call__()
            GraphSchema.get_system_prompt()
            TinyLlama extracts entities + relationships
            returns JSON: {nodes: [], edges: []}
            ↓
        Neo4jIndexer.write(batch)
            MERGE (node:Entity {name: n.id})
            MERGE (source)-[r:RELATED]->(target)
            → knowledge graph built in Neo4j
        ↓
    Job complete — documents searchable
```


### Phase 7 — User Sends a Chat Message

``` bash
POST api.your-rag-platform.com/api/v1/chat/stream
Authorization: Bearer eyJ...
{
    "message": "Compare HPA vs VPA in Kubernetes",
    "session_id": "sess-123",
    "use_hyde": true,
    "use_query_rewriter": true
}
    ↓
AWS Load Balancer receives request
    ↓
Nginx Ingress routes /chat → api-service:80
    ↓
api-service routes to API pod:8000
    ↓
FastAPI routes/chat.py::chat_stream()

1. JWT validation
   get_current_user() decodes Bearer token
   verifies signature with JWT_SECRET_KEY
   extracts user_id, role, permissions

2. Semantic cache check
   SemanticCache.get_cached_response(message)
       embed_client.embed_query(message)
           → POST embed-service:8000/embed
           → 768-dim vector returned
       qdrant_client.search_collection(
           "semantic_cache", vector, threshold=0.95)
       score > 0.95? → cache HIT
           stream cached answer instantly
           BackgroundTask: save to PostgreSQL
           return StreamingResponse
       score < 0.95? → cache MISS → continue

3. Load conversation history
   postgres_memory.get_history(session_id, limit=6)
       SELECT from chat_history ORDER BY created_at DESC LIMIT 6
       reversed to chronological order

4. Query enhancement (optional)
   query_rewriter.py::rewrite_query(message, history)
       LLM resolves coreferences
       "How much does it cost?" → "How much does Kubernetes cost?"
   hyde.py::generate_hypothetical_document(query)
       LLM generates fake paragraph using domain vocabulary
       better vector similarity match

5. LangGraph agent starts
   agent_app.astream(initial_state)

   PLANNER NODE
       llm_client.chat_completion(SYSTEM_PROMPT + query)
           → POST llm-service:8000/llm
           → TinyLlama decides action
       returns JSON:
           action: "retrieve"
           refined_query: "HPA vs VPA cost comparison Kubernetes"
           reasoning: "specific technical question requiring docs"
           tool_choice: null
       yield {"type": "status", "node": "planner"}

   CONDITIONAL ROUTING
       action == "retrieve" → RETRIEVER NODE
       action == "direct_answer" → RESPONDER NODE
       action == "tool_use" → TOOL NODE

   RETRIEVER NODE (if retrieve)
       embed_client.embed_query(refined_query)
           → 768-dim vector

       asyncio.gather() — both searches fire simultaneously:

       run_vector_search():
           qdrant_client.search(vector, limit=5)
               HNSW cosine similarity search
               returns top 5 chunks with metadata
               formatted: "text [Source: filename]"

       run_graph_search():
           LLM extracts entities: ["HPA", "VPA", "Kubernetes"]
           neo4j_client.query(fixed_cypher, {"query": query})
               CALL db.index.fulltext.queryNodes()
               MATCH (node)-[r]->(neighbor)
               returns relationship triples

       merge + deduplicate (graph priority)
       state["documents"] = combined_docs
       yield {"type": "status", "node": "retriever"}

   RESPONDER NODE
       context_str = join(documents)
       llm_client.chat_completion(
           system: "You are Enterprise Assistant, cite sources"
           user: context + question
           temperature: 0.3
       )
           → POST llm-service:8000/llm
           → TinyLlama generates answer
       state["messages"].append({"role": "assistant", "content": answer})
       yield {"type": "status", "node": "responder"}
       yield {"type": "answer", "content": answer}

6. Post-processing
   postgres_memory.add_message(session_id, "user", message, user_id)
   postgres_memory.add_message(session_id, "assistant", answer, user_id)
       INSERT INTO chat_history ...
   semantic_cache.set_cached_response(message, answer)
       embed query → upsert to Qdrant semantic_cache

7. StreamingResponse closes
   Client received NDJSON stream:
       {"type": "status", "node": "planner"}
       {"type": "status", "node": "retriever"}
       {"type": "status", "node": "responder"}
       {"type": "answer", "content": "HPA scales pods horizontally..."}
```


### Phase 8 — User Submits Feedback

``` bash
POST /api/v1/feedback
{"session_id": "sess-123", "message_id": 42, "score": 1, "comment": "Great answer"}
    ↓
JWT validated → user_id extracted
    ↓
INSERT INTO feedback (session_id, user_id, message_id, score, comment)
    ↓
feedback accumulates → used for RLHF fine-tuning
```


### Phase 9 — Upload a New Document

``` bash
POST /api/v1/upload/generate-presigned-url
{"filename": "k8s-guide.pdf", "content_type": "application/pdf"}
    ↓
JWT validated → user_id extracted
    ↓
uuid4() → file_id
s3_key = uploads/user-id/file-id.pdf
    ↓
asyncio.to_thread(s3_client.generate_presigned_url)
    → signed URL valid 1 hour, PUT only
    ↓
browser PUT 500MB PDF directly to S3 (API never touched)
    ↓
S3 event → s3_event_handler.py → Ray ingestion job
    ↓
document processed → vectors in Qdrant → graph in Neo4j
    ↓
document searchable in next chat query
```


### Phase 10 — Teardown

``` bash
make infra-destroy
# runs cleanup.sh then terraform destroy
```

``` bash
cleanup.sh:
    helm uninstall api
    helm uninstall qdrant
    helm uninstall kuberay-operator
    helm uninstall external-secrets
    helm uninstall ingress-nginx
    kubectl delete -f deploy/ray/
    kubectl delete -f deploy/secrets/
    sleep 20  ← wait for Load Balancers to deregister
        ↓
terraform destroy:
    deletes all 38-48 resources in reverse dependency order
    EKS node group → EKS cluster → RDS → Redis →
    NAT Gateway → subnets → VPC → ECR → S3 → IAM
        ↓
    state updated in S3
    DynamoDB lock released
        ↓
Zero AWS resources running
Zero charges accumulating
```

---

### Everything at a glance

``` 
MANUAL SETUP (once)
    AWS Console → S3 state bucket + DynamoDB lock table
    aws configure → credentials

INFRASTRUCTURE (make infra ~20 mins)
    Terraform → VPC, EKS, RDS, Redis, S3, ECR, IAM

SECRETS (manual after infra)
    AWS Secrets Manager → db_creds, api_keys

IMAGES (make docker ~10 mins)
    Dockerfile → rag-api image → ECR
    models/Dockerfile → rag-models image → ECR

CLUSTER BOOTSTRAP (make bootstrap ~15 mins)
    kubectl connect → EKS
    KubeRay operator → manages Ray
    External Secrets → fetches secrets from AWS
    Nginx → load balancer + routing
    Qdrant → vector database
    Ray cluster → head + workers
    Ray Serve embed → embedding endpoint
    Ray Serve LLM → TinyLlama endpoint
    Nginx ingress rules → URL routing
    API Helm chart → FastAPI pods running

DOCUMENTS (bulk_upload_s3.py)
    S3 → Ray ingestion job
    parse → chunk → embed → index Qdrant + Neo4j

LIVE (users chatting)
    JWT auth → cache check → history → LangGraph
    planner → retriever → responder → stream answer
    save to PostgreSQL → update cache

TEARDOWN (make infra-destroy)
    helm uninstall → kubectl delete → terraform destroy
```