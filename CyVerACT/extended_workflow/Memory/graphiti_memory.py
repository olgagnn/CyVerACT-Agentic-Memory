import os
import asyncio
from datetime import datetime
from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver  # <-- ΝΕΟ IMPORT ΕΔΩ
from graphiti_core.nodes import EpisodeType
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

class GraphitiMemoryManager:
    def __init__(self):
        driver = Neo4jDriver(
            uri=os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "agentmemory"),
            database="episodic"  
        )
        
        self.graphiti = Graphiti(graph_driver=driver)

    async def search_memory(self, query: str, group_id: str, limit: int = 5) -> str:
        """
        Search Graphiti for similar past interactions asynchronously.
        """
        try:
            results = await self.graphiti.search(
                query=query,
                group_id=group_id,
                limit=limit
            )

            if not results:
                return ""

            # Edges in Graphiti contain the .fact attribute
            return "\n".join(f"- {r.fact}" for r in results)  
        except Exception as e:
            print(f"[Graphiti] Search Error: {e}")
            return ""

    async def add_episode(
        self,
        question: str,
        final_cypher: str,
        result: str | None = None,
        errors: list[str] | None = None,
        attempts: int | None = None,
    ):
        """
        Format and store an interaction episode asynchronously.
        """
        outcome = "SUCCESS" if not errors else "FAILED"
        errors_text = "\n".join(errors) if errors else "None"

        episode_content = f"""
Cypher Agent Interaction

User Question:
{question}

Final Cypher:
{final_cypher}

Execution Result:
{result}

Errors:
{errors_text}

Attempts:
{attempts}

Outcome:
{outcome}
"""

        try:
            await self.graphiti.add_episode(
                name="cypher_agent_interaction",
                episode_body=episode_content,
                source=EpisodeType.text,
                source_description="Cypher agent interaction",
                reference_time=datetime.now(),
                group_id="cypher_agent_global", # Crucial for namespacing in the same Neo4j DB
            )
            print("[Graphiti] Episodic memory stored.")
        except Exception as e:
            print(f"[Graphiti] Episodic write error: {e}")