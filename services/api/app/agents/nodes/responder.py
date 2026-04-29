from services.api.app.agents.state import AgentState
from services.api.app.clients.ray_llm import llm_client

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
    
    # Return dictionary to update state (add the AI message)
    return {
        "messages": [{"role": "assistant", "content": answer}]
    }