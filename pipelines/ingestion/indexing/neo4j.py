import os
from typing import Any, Dict
from neo4j import GraphDatabase


class Neo4jIndexer:
    """
    Ray Data terminal sink — same callable-class shape as QdrantIndexer
    (see its docstring for why this replaced write_datasource()). Batch is
    column-oriented: batch["graph_nodes"][i] / batch["graph_edges"][i] are
    the node/edge lists GraphExtractor produced for chunk i.
    """
    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://neo4j-cluster:7687")   # neo4j-cluster = Kubernetes service name
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        # Idempotent — graph_search.py's fulltext lookup needs this index
        # to exist; created here rather than as a separate manual migration
        # step, same lazy-init spirit as qdrant_client.init_collections().
        with self.driver.session() as session:
            session.run(
                "CREATE FULLTEXT INDEX entity_index IF NOT EXISTS FOR (n:Entity) ON EACH [n.name]"
            )

    def __call__(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """Every node/edge tagged with corpus_id so graph_search.py's
        queries can filter by tenant — without this, entity names from one
        corpus would be visible/connectable to another corpus's questions."""
        import json

        all_nodes = []
        all_edges = []
        n = len(batch.get("corpus_id", []))

        for i in range(n):
            corpus_id = batch["corpus_id"][i]
            # graph_nodes/graph_edges arrive as JSON strings (see
            # graph/extractor.py's docstring — ragged-shape object arrays
            # broke Arrow's column type inference; plain strings don't).
            nodes = json.loads(batch.get("graph_nodes", ["[]"] * n)[i])
            edges = json.loads(batch.get("graph_edges", ["[]"] * n)[i])
            for node in nodes:
                all_nodes.append({**node, "corpus_id": corpus_id})
            for edge in edges:
                all_edges.append({**edge, "corpus_id": corpus_id})

        if all_nodes or all_edges:
            with self.driver.session() as session:
                session.execute_write(self._merge_graph_data, all_nodes, all_edges)

        return batch

    @staticmethod
    def _merge_graph_data(tx, nodes, edges):
        """Idempotent MERGE (upsert). Entity identity is scoped to
        (name, corpus_id) — the same entity name in two different corpora
        is two different nodes, not one shared node, matching the
        session-isolation guarantee the rest of the app relies on."""
        if nodes:
            tx.run(
                """
                UNWIND $nodes AS n
                MERGE (node:Entity {name: n.id, corpus_id: n.corpus_id})
                SET node.type = n.type
                """,
                nodes=nodes,
            )
        if edges:
            tx.run(
                """
                UNWIND $edges AS e
                MATCH (source:Entity {name: e.source, corpus_id: e.corpus_id})
                MATCH (target:Entity {name: e.target, corpus_id: e.corpus_id})
                MERGE (source)-[r:RELATED {type: e.type}]->(target)
                """,
                edges=edges,
            )
