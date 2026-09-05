from services.api.app.agents.state import AgentState
from services.api.app.clients.llm.factory import llm_client

async def generate_node(state: AgentState) -> dict:
    """
    Synthesizes the final answer using retrieved documents.
    """
    query = state["current_query"]
    documents = state["documents"] or []
    
    # Construct Context String
    context_str = "\n\n".join(documents)
    
    answer = await llm_client.chat_completion(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful Enterprise Assistant. "
                    "Always cite sources using [Source: Filename]. "
                    "If the answer is not in the context, say "
                    "'I don't have that information in my documents.' "
                    "Be concise and professional."
                )
            },
            {
                "role": "user",
                "content": f"Context:\n{context_str}\n\nQuestion:\n{query}"
            }
        ],
        temperature=0.3
    )

    # backend_used: FailoverLLMClient (LLM_BACKEND=api) tracks which of
    # Groq/OpenRouter actually answered; manual-select backends (ollama/
    # vllm_local/vllm_modal) have no failover concept, so their class name
    # is the whole story. Phase 5's cache stores this alongside the answer.
    backend_used = getattr(llm_client, "last_backend_used", "") or llm_client.__class__.__name__

    # Return dictionary to update state (add the AI message)
    return {
        "messages": [{"role": "assistant", "content": answer}],
        "backend_used": backend_used,
    }