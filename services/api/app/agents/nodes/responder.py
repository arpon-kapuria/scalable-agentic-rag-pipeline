from services.api.app.agents.state import AgentState
from services.api.app.agents.tokenCount import _count_tokens
from services.api.app.clients.ray_llm import llm_client
from libs.observability.metrics import TOKEN_USAGE
import tiktoken

async def generate_node(state: AgentState) -> dict:
    """
    Synthesizes the final answer using retrieved documents.
    """
    query = state["current_query"]
    documents = state["documents"] or []
    
    # Construct Context String
    context_str = "\n\n".join(documents)

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
        ]

    # Count prompt tokens before LLM call
    prompt_tokens = _count_tokens(messages)

    answer = await llm_client.chat_completion(
        messages=messages,
        temperature=0.3
    )

    # Count completion tokens after LLM responds
    completion_tokens = _count_tokens([{"role": "assistant", "content": answer}])

    # Track token usage in Prometheus
    TOKEN_USAGE.labels(model="tinyllama", type="prompt").inc(prompt_tokens)
    TOKEN_USAGE.labels(model="tinyllama", type="completion").inc(completion_tokens)
    
    # Return dictionary to update state (add the AI message)
    return {
        "messages": [{"role": "assistant", "content": answer}]
    }