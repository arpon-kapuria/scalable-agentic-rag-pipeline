from typing import Literal

# Allowed Node Labels (Entities)
# We restrict the LLM to only find these types of entities to keep the graph clean.
VALID_NODE_LABELS = Literal[
    "Person",
    "Organization",
    "Location",
    "Concept",
    "Document",
    "Event",
    "Product"
]

# Allowed Edge Types (Relationships)
VALID_RELATION_TYPES = Literal[
    "WORKS_FOR",
    "LOCATED_IN",
    "RELATES_TO",
    "MENTIONS",
    "PART_OF",
    "CREATED_BY",
    "HAS_FEATURE"
]

class GraphSchema:
    """
    Central source of truth for the Knowledge Graph structure.
    Used by the Extractor prompt to ensure consistency.
    """
    @staticmethod
    def get_system_prompt() -> str:
        return f"""
        You are a Knowledge Graph extraction engine.
        Extract nodes and relationships from the text.

        Allowed Node Labels: {VALID_NODE_LABELS.__args__}
        Allowed Relationship Types: {VALID_RELATION_TYPES.__args__}

        Return JSON format only:
        {{
            "nodes": [{{"id": "Name", "type": "Label"}}],
            "edges": [{{"source": "Name", "target": "Name", "type": "RELATION"}}]
        }}
        """

    @staticmethod
    def get_batch_system_prompt() -> str:
        """
        Batched variant (Bug 2 fix): extracts from multiple numbered text
        segments in one call instead of one call per chunk — cuts LLM call
        volume by the batch factor (main driver of the 429/rate-limit
        pressure seen during Phase 3/4 testing), and gives the model more
        cross-chunk context per call, which also tends to improve entity
        resolution (same pattern GraphRAG-style pipelines use).
        """
        return f"""
        You are a Knowledge Graph extraction engine.
        You will be given several numbered text segments. Extract nodes
        and relationships from EACH segment separately.

        Allowed Node Labels: {VALID_NODE_LABELS.__args__}
        Allowed Relationship Types: {VALID_RELATION_TYPES.__args__}

        Return JSON format only, one entry per segment, in the same order
        they were given, even if a segment has no nodes/edges (use empty
        lists, not null, and never omit a segment):
        {{
            "segments": [
                {{"nodes": [{{"id": "Name", "type": "Label"}}], "edges": [{{"source": "Name", "target": "Name", "type": "RELATION"}}]}},
                ...
            ]
        }}
        """
