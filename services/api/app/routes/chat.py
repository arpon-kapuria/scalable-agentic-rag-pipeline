"""
POST /stream
      ↓
Check semantic cache → hit? stream cached answer instantly
      ↓ miss
Load conversation history from PostgreSQL
      ↓
[Optional] Rewrite query to resolve coreferences
      ↓
[Optional] Generate hypothetical document (HyDE) for better retrieval
      ↓
Initialize LangGraph agent state
      ↓
Stream agent events (planner → retriever → responder)
      ↓
Save to memory + update cache in background
"""

import uuid
import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.api.app.auth.jwt import get_current_user
from services.api.app.cache.semantic import SemanticCache, semantic_cache as global_cache
from services.api.app.memory.postgres import PostgresMemory, postgres_memory as global_memory
from services.api.app.clients.ray_llm import RayLLMClient, llm_client as global_llm
from services.api.app.agents.graph import agent_app
from services.api.app.agents.state import AgentState
from services.api.app.enhancers.query_rewriter import rewrite_query
from services.api.app.enhancers.hyde import generate_hypothetical_document

router = APIRouter()
logger = logging.getLogger(__name__)

# --- Dependency Providers (DI) ---

def get_semantic_cache() -> SemanticCache:
    return global_cache

def get_memory() -> PostgresMemory:
    return global_memory

def get_llm_client() -> RayLLMClient:
    return global_llm

# --- Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's query")
    session_id: Optional[str] = Field(default=None, description="UUID for the conversation thread")

    # Optional enhancement flags — both default to False
    # Set to True to enable query rewriting and HyDE
    use_query_rewriter: bool = Field(default=False, description="Resolve coreferences using conversation history")
    use_hyde: bool = Field(default=False, description="Generate hypothetical document for better retrieval")

# --- Routes ---

@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    cache: SemanticCache = Depends(get_semantic_cache),
    memory: PostgresMemory = Depends(get_memory),
    llm: RayLLMClient = Depends(get_llm_client)
):
    """
    Main Chat Endpoint (Streaming).
    Orchestrates the RAG flow: Cache -> Enhance -> History -> Agent -> Stream.

    Optional enhancements (controlled per request):
        use_query_rewriter: resolves "it", "they", "that" using conversation history
        use_hyde: generates a hypothetical document to improve vector similarity search
    """
    # 1. Setup Session Context
    session_id = req.session_id or str(uuid.uuid4())
    user_id = user["id"]

    logger.info(f"Chat request for session {session_id} from user {user_id}")

    # 2. Semantic Cache Check (Fast Path)
    cached_ans = await cache.get_cached_response(req.message)

    if cached_ans:
        logger.info(f"Cache hit for session {session_id}")

        async def stream_cache():
            yield json.dumps({
                "type": "answer",
                "content": cached_ans,
                "session_id": session_id
            }) + "\n"

        background_tasks.add_task(memory.add_message, session_id, "user", req.message, user_id)
        background_tasks.add_task(memory.add_message, session_id, "assistant", cached_ans, user_id)

        return StreamingResponse(stream_cache(), media_type="application/x-ndjson")

    # 3. Load Conversation History
    history_objs = await memory.get_history(session_id, limit=6)
    history_dicts = [
        {"role": msg.role, "content": msg.content} for msg in history_objs
    ]

    # 4. Query Enhancement (Optional)
    # Start with the raw user message
    enhanced_query = req.message

    # Step A — Query Rewriter: resolve coreferences using history
    # "How much does it cost?" + history → "How much does Kubernetes cost?"
    if req.use_query_rewriter and history_dicts:
        try:
            enhanced_query = await rewrite_query(enhanced_query, history_dicts)
            logger.info(f"Query rewritten: '{req.message}' → '{enhanced_query}'")
        except Exception as e:
            # Non-fatal — fall back to original query
            logger.warning(f"Query rewriter failed, using original: {e}")
            enhanced_query = req.message

    # Step B — HyDE: generate hypothetical document for better vector similarity
    # "What is Kubernetes?" → fake paragraph using K8s vocabulary → better embedding match
    if req.use_hyde:
        try:
            enhanced_query = await generate_hypothetical_document(enhanced_query)
            logger.info(f"HyDE query generated for: '{req.message}'")
        except Exception as e:
            # Non-fatal — fall back to rewritten or original query
            logger.warning(f"HyDE generation failed, using previous query: {e}")

    # 5. Append current user message to history
    history_dicts.append({"role": "user", "content": req.message})

    # 6. Initialize Agent State
    # Note: current_query uses the enhanced version for better retrieval
    #       messages uses the original message to preserve conversation history correctly
    initial_state = AgentState(
        messages=history_dicts,
        current_query=enhanced_query,   # ← enhanced query for retrieval
        documents=[],
        plan=[],
        action=""
    )

    # 7. Streaming Generator
    async def event_generator() -> AsyncGenerator[str, None]:
        final_answer = ""

        try:
            async for event in agent_app.astream(
                initial_state,
                config={"configurable": {"llm": llm, "user_id": user_id}}
            ):
                node_name = list(event.keys())[0]
                node_data = event[node_name]

                # Emit status for every node so frontend can show progress
                yield json.dumps({
                    "type": "status",
                    "node": node_name,
                    "session_id": session_id,
                    "info": f"Completed step: {node_name}"
                }) + "\n"

                # Capture final answer from responder node
                if node_name == "responder":
                    if "messages" in node_data and node_data["messages"]:
                        ai_msg = node_data["messages"][-1]
                        final_answer = ai_msg.get("content", "")

                        yield json.dumps({
                            "type": "answer",
                            "content": final_answer,
                            "session_id": session_id
                        }) + "\n"

            # 8. Post-Processing
            if final_answer:
                await memory.add_message(session_id, "user", req.message, user_id)
                await memory.add_message(session_id, "assistant", final_answer, user_id)
                await cache.set_cached_response(req.message, final_answer)

        except Exception as e:
            logger.error(f"Error in chat stream: {e}", exc_info=True)
            yield json.dumps({
                "type": "error",
                "content": "An internal error occurred."
            }) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")