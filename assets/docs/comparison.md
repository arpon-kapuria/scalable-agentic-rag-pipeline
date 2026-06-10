# Setup Comparison: minimal (main) vs full-scale (dev/aws-full-scale)

---

## 1. LLM & Inference Stack

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Primary LLM | TinyLlama 1.1B | Meta-Llama-3-70B-Instruct |
| Light-task LLM | TinyLlama 1.1B (same) | Meta-Llama-3-8B-Instruct |
| Inference engine | HuggingFace `transformers` | vLLM `AsyncLLMEngine` |
| Quantization | None (float32) | AWQ 4-bit |
| Context window | 2048 tokens | 8192 tokens |
| Concurrent sequences | 4 | 128 (70B) / 256 (8B) |
| Tensor parallelism | None | 4 GPUs (70B) / 1 GPU (8B) |
| GPU memory utilization | N/A | 90% (70B) / 85% (8B) |
| LLM replicas (max) | 2 | 10 |
| Max tokens per response | 512 | 1024 |

**What this means:** vLLM's `AsyncLLMEngine` uses continuous batching — it doesn't wait for a batch to fill up, it streams tokens and slots in new requests as sequences finish. HuggingFace `generate()` is synchronous and processes one request at a time. This is the single biggest throughput difference in the system. At scale, vLLM on 70B-AWQ can handle ~128 concurrent users per GPU replica; TinyLlama on CPU handles ~4.

---

## 2. Embedding Service

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Model | BAAI/bge-m3 | BAAI/bge-m3 |
| Device | CPU (float32) | CUDA (float16) |
| torch.compile | Removed | Enabled |
| Batch size | 8 | 32 |
| Max sequence length | 512 | 8192 |
| GPU fraction per replica | 0 | 0.5 (fractional sharing) |
| Max replicas | 2 | 5 |
| Requests per replica target | 10 | 50 |

**What this means:** `num_gpus: 0.5` is Ray's fractional GPU allocation — two embedding replicas share one physical GPU. This is how you run embedding and LLM inference on the same GPU node without conflict. float16 on CUDA is ~2x faster than float32 on CPU for matrix ops. `torch.compile` (PyTorch 2.0+) JIT-compiles the model graph, giving another 10-30% throughput gain on repeated forward passes.

---

## 3. Reranker

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Model | BAAI/bge-reranker-v2-m3 (commented out) | BAAI/bge-reranker-v2-m3 |
| Status | Disabled — pipeline node not implemented | Configured (float16, batch 16) |
| Purpose | Re-scores retrieved chunks before LLM | Same |

**What this means:** The reranker sits between retrieval and the LLM. After Qdrant returns top-K chunks by cosine similarity, the reranker cross-encodes each (query, chunk) pair and re-scores them. Cross-encoders are more accurate than bi-encoders for relevance scoring because they see both query and document together, not as separate embeddings. The tradeoff is latency — it's an extra model call per query. Absent in minimal because it requires a GPU replica.

---

## 4. Ray Cluster

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Ray image (head) | `ray:2.9.0-py310` (CPU) | `ray:2.9.0-py310-gpu` |
| Head node CPU | 1 core / 2Gi | 2 core / 8Gi |
| CPU worker: CPU/RAM | 1 core / 2Gi | 8 core / 32Gi |
| CPU worker max replicas | 3 | 50 |
| CPU instance family | t3 (via Karpenter) | c6i (compute-optimized) |
| GPU worker group | Removed entirely | 0–20 replicas, 1 GPU each |
| GPU instance category | N/A | g5 / p4d (g-gen > 4) |
| GPU capacity type | N/A | on-demand + spot mix |
| GPU TTL when empty | N/A | 30 seconds |

**What this means:** c6i instances are compute-optimized Intel Gen 6 — designed for CPU-heavy workloads like PDF parsing, text chunking, and tokenization. t3 is general-purpose burstable — fine for light work but throttles under sustained CPU load (T-series credits). The GPU worker `ttlSecondsAfterEmpty: 30` is critical for cost — a GPU node spins down 30 seconds after the last task, so you're not paying for idle GPU time. This is Karpenter's core value proposition over the old Cluster Autoscaler.

---

## 5. Autoscaling

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| CPU worker max | 3 workers, 1 CPU each = 3 CPU total | 50 workers, 8 CPU each = 400 CPU total |
| GPU worker max | Disabled | 20 workers × 1 GPU = 20 GPUs |
| Karpenter CPU cap | 8 CPU hard limit | 1000 CPU hard limit |
| Karpenter GPU cap | N/A | 100 GPUs hard limit |
| Idle timeout | 5 minutes | 5 minutes |

**What this means:** The CPU cap of 8 in minimal is a hard financial guardrail — Karpenter will refuse to provision nodes beyond that total CPU count regardless of pending pods. In full-scale, the 1000 CPU / 100 GPU caps are safety ceilings, not expected operating points. The real autoscaling driver is Ray's `target_num_ongoing_requests_per_replica` — when that threshold is exceeded, Ray Serve requests a new replica, which triggers a pending pod, which triggers Karpenter to provision a node.

---

## 6. EKS & Node Groups

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| K8s version | 1.33 | 1.32 |
| System node instance | t3.medium | m6i.large |
| System node min/desired | 1 | 2 |
| System node max | 3 | 5 |
| System node taint | None (removed) | `CriticalAddonsOnly=true:NoSchedule` |
| KMS encryption | Disabled | Enabled (implied by no override) |
| IRSA | Enabled (both) | Enabled (both) |

**What this means:** The taint on system nodes in full-scale is a hard scheduling boundary — app pods (Ray workers, API pods) cannot land on the system node group even if Karpenter hasn't provisioned a new node yet. This prevents a Ray ingestion job from starving CoreDNS or Karpenter itself of CPU, which would cause cascading failures. In minimal, removing the taint was necessary because with only 1 node you have no choice — everything runs there. m6i.large (2 vCPU, 8GB) vs t3.medium (2 vCPU, 4GB) — the memory difference matters because CoreDNS, Karpenter, the metrics server, and the ingress controller all run on the system node simultaneously.

---

## 7. VPC & Networking

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Availability zones | 2 (a, b) | 3 (a, b, c) |
| Public subnets | 2 | 3 |
| Private subnets | 2 | 3 |
| Database subnets | 2 | 3 |
| NAT Gateway | Single (1 total) | One per AZ (3 total) |
| Single point of failure | Yes (NAT) | No |

**What this means:** A single NAT Gateway saves ~$65/month (you pay per AZ). The tradeoff is that if `us-east-1a` has an AZ outage, all private subnet egress traffic from `us-east-1b` is also broken because it routes through the single NAT in `1a`. In production, one NAT per AZ means an AZ failure only affects pods in that AZ — the other AZs keep working independently. This is the network-level definition of high availability.

---

## 8. PostgreSQL (Chat History)

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Engine | Standard RDS PostgreSQL 15 | Aurora PostgreSQL 15.3 |
| Instance class | db.t3.micro | db.serverless (Aurora Serverless v2) |
| Storage | 20GB fixed | Serverless (auto-managed) |
| HA / Multi-AZ | No | Yes (2 instances: writer + reader) |
| ACU scaling | N/A | 2–64 ACUs |
| Backup retention | 1 day | Default (7 days) |
| Final snapshot on destroy | Skipped | Kept |

**What this means:** Aurora Serverless v2 scales compute in increments of 0.5 ACU (1 ACU ≈ 2GB RAM). At 2 ACU minimum it's always ready, at 64 ACU maximum it handles peak chat traffic without pre-provisioning. Standard RDS t3.micro is fixed compute — if chat traffic spikes, queries queue up and latency grows. The writer/reader split in Aurora means read-heavy workloads (fetching chat history) go to the reader instance, keeping the writer free for inserts.

---

## 9. Redis (Semantic Cache)

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Resource type | `aws_elasticache_cluster` | `aws_elasticache_replication_group` |
| Node type | cache.t3.micro | cache.t4g.medium |
| Nodes | 1 (no replica) | 2 (primary + replica) |
| At-rest encryption | Disabled | Enabled |
| In-transit encryption | Disabled | Enabled (TLS) |
| Architecture | Graviton2 (t4g) | Intel (t3) |

**What this means:** `aws_elasticache_cluster` is a standalone node — if it goes down, your semantic cache and session memory are gone until it restarts, and all in-flight requests either fail or miss cache. `aws_elasticache_replication_group` with 2 nodes gives automatic failover — if the primary fails, the replica is promoted in ~30 seconds with no data loss. t4g (Graviton2) is ARM-based and ~20% cheaper per unit of performance than t3 for Redis workloads.

---

## 10. S3

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Bucket name suffix | `-dev-001` | `-prod-001` |
| `force_destroy` | true | false |
| Transfer Acceleration | Removed | Enabled |
| Lifecycle / Intelligent Tiering | Removed | After 30 days |
| CORS allowed origins | `*` (open) | `https://your-rag-domain.com` |
| Versioning | Enabled (both) | Enabled (both) |

**What this means:** Transfer Acceleration routes uploads through the nearest AWS Edge location (CloudFront PoP) rather than directly to the S3 region. For users uploading 100MB+ documents from outside us-east-1, this can cut upload time by 50-70%. Intelligent Tiering automatically moves objects not accessed in 30 days to cheaper storage tiers — relevant when the corpus grows to thousands of documents. `force_destroy = true` in dev lets you run `terraform destroy` without manually emptying the bucket first — never acceptable in prod where data loss would be catastrophic.

---

## 11. Ingress / Rate Limiting

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Rate limiting | NGINX annotations (`limit-rps: 10`, `limit-connections: 5`) | None in Ingress (handled by gateway/rate_limit.lua) |
| Path prefixes | `/api/v1/chat`, `/api/v1/upload`, `/api/v1/auth`, `/api/v1/feedback` | `/chat`, `/upload` |
| Body size limit | 50m (both) | 50m (both) |

---

## 12. ECR

| Aspect | main (minimal) | dev/aws-full-scale |
|---|---|---|
| Sandbox repo | Commented out | Not present (different scope) |
| Lifecycle policy | Keep last 5 images (both) | Same |
| Scan on push | Enabled (both) | Same |

---

## Summary: What Each Change Actually Controls

| Change | Controls |
|---|---|
| TinyLlama → Llama-3-70B + vLLM | Generation quality, throughput, concurrent users |
| HuggingFace generate → AsyncLLMEngine | Continuous batching — the difference between 4 and 128 concurrent requests per replica |
| CPU embedding → CUDA + torch.compile | Embedding throughput during ingestion and query rewriting |
| Reranker enabled | Retrieval precision — cross-encoder re-scoring before LLM call |
| t3 workers → c6i workers (1→8 CPU) | Ingestion pipeline speed — chunking, parsing, graph extraction |
| GPU worker group (0–20) | Enables embedding + LLM inference on GPU at all |
| Single NAT → per-AZ NAT | Network-level AZ fault isolation |
| t3.micro RDS → Aurora Serverless v2 | Database elasticity under variable chat load |
| Single Redis → replication group + TLS | Cache HA + data security in transit |
| S3 Transfer Acceleration + Intelligent Tiering | Upload latency for global users + long-term storage cost |
| System node taint | Prevents app workloads starving cluster infrastructure |
| 2 AZ → 3 AZ | True multi-AZ HA for all stateful services |