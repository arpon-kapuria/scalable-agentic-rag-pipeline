from typing import TypedDict, Annotated, List
import operator

class AgentState(TypedDict):
    """
    The state object passed between nodes in the LangGraph.
    Tracks the conversation history and current step data.
    """
    # Using 'operator.add' means new messages are appended, not overwritten
    messages: Annotated[List[dict], operator.add] 
    
    # Context retrieved from RAG (Vector + Graph)
    documents: List[str] 
    
    # The current question being processed
    current_query: str 
    
    # Internal scratchpad for the planner
    plan: List[str]

    action: str

    tool_choice: str 

    tool_input: str

    # Multi-tenant scoping (Phase 2) — every retrieval tool call filters by
    # this. Set once in chat.py from the session cookie's corpus_id, never
    # derived from user input at any node.
    corpus_id: str

    # Phase 5: populated by whichever node actually produced the answer
    # (retriever/tool/responder) — cached alongside the answer itself so
    # a cache hit can still report accurate metadata (locked design: cache
    # the full response, not just the answer text).
    tool_used: str
    backend_used: str
    sources: list[str]