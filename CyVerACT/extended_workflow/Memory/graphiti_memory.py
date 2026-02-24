import os
import asyncio
from datetime import datetime
from graphiti_core import Graphiti
from graphiti_core.driver.neo4j_driver import Neo4jDriver  
from graphiti_core.nodes import EpisodeType
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Setting up graphiti with neo4j driver based on the documentation
class GraphitiMemoryManager:
    def __init__(self):
        driver = Neo4jDriver(
            uri=os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "agentmemory"),
            database="episodic"  
        )
        
        self.graphiti = Graphiti(graph_driver=driver)

    async def search_memory(self, query: str) -> str:
        """
        Retrieves the most recent context from memory. For example: 
        USER QUESTION 1: Who directed the movie The Matrix? (SYSTEM answers)
        USER QUESTION 2: Tell me the plot of that movie? (SYSTEM remembers which movie)
        """
        try:
            # Using await here to get the right results + database name to be sure
            records, summary, keys = await self.graphiti.driver.execute_query(
                "MATCH (e:Episodic) RETURN e.content AS content ORDER BY e.created_at DESC LIMIT 1",
                database_="episodic"
            )
            
            if not records:
                return ""
                
            return f"- Previous interaction:\n{records[0]['content']}"
            
        except Exception as e:
            print(f"[Graphiti] History Retrieval Error: {e}")
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
        Formatting and storing an agent episode
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
                reference_time=datetime.now()
            )
            print("[Graphiti] Episodic memory stored.")
        except Exception as e:
            print(f"[Graphiti] Episodic write error: {e}")