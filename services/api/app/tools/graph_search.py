import json

from services.api.app.clients.llm.factory import llm_client
from services.api.app.clients.neo4j import neo4j_client

SYSTEM_PROMPT = """
You are a Knowledge Graph Helper.
Extract the core entities from the user's question to perform a search.

Question: {question}

Output JSON only:
{{
    "entities": ["list", "of", "names"]
}}
"""


async def search_graph_tool(question: str, corpus_id: str) -> str:
    """
    Safely searches the graph by extracting entities and looking up their
    neighborhoods, scoped to one corpus_id. Prevents Cypher Injection —
    entity names come from the LLM as a parameter, never interpolated
    into the query string.
    """
    try:
        response_text = await llm_client.chat_completion(
            messages=[{"role": "system", "content": SYSTEM_PROMPT.format(question=question)}],
            temperature=0.0,
            json_mode=True,
        )
        data = json.loads(response_text)
        entities = data.get("entities", [])

        if not entities:
            return "No specific entities identified to search."

        cypher_query = """
        UNWIND $names AS target_name
        CALL db.index.fulltext.queryNodes("entity_index", target_name) YIELD node, score
        WHERE node.corpus_id = $corpus_id
        MATCH (node)-[r]-(neighbor {corpus_id: $corpus_id})
        RETURN node.name AS source, type(r) AS rel, neighbor.name AS target
        LIMIT 10
        """

        results = await neo4j_client.query(cypher_query, {"names": entities, "corpus_id": corpus_id})

        if not results:
            return "No knowledge graph connections found."

        return str(results)

    except Exception as e:
        return f"Graph search error: {str(e)}"
