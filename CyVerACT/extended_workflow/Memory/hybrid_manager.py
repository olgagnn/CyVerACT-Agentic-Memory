import os
import asyncio
import nest_asyncio

# Apply nest_asyncio to allow asyncio.run() within an already running event loop 
# (useful if you are running this in Jupyter, FastAPI, or similar environments).
nest_asyncio.apply()

# Import Cognee 
try:
    from Memory.cognee_memory import CogneeMemoryManager
    COGNEE_AVAILABLE = True
except ImportError:
    COGNEE_AVAILABLE = False
    print("[Hybrid Memory Manager] Cognee not found.")

# Import Graphiti 
try:
    from Memory.graphiti_memory import GraphitiMemoryManager
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    print("[Hybrid Memory Manager] Graphiti not found.")


class HybridMemoryManager:
    def __init__(self):
        self.cognee = None
        self.graphiti = None
        
        if COGNEE_AVAILABLE:
            try:
                self.cognee = CogneeMemoryManager()
                print("[Hybrid Memory Manager] Cognee Connected.")
            except Exception as e:
                print(f"[Hybrid Memory Manager] Cognee Init Failed: {e}")

        if GRAPHITI_AVAILABLE:
            try:
                self.graphiti = GraphitiMemoryManager()
                print("[Hybrid Memory Manager] Graphiti Connected.")
            except Exception as e:
                print(f"[Hybrid Memory Manager] Graphiti Init Failed: {e}")

    # -----------------------------
    # PROCEDURAL MEMORY - COGNEE
    # -----------------------------
    def get_procedural_lessons(self, query: str) -> str:
        """
        Retrieve past procedural lessons / mistakes from Cognee
        """
        if self.cognee:
            return self.cognee.get_relevant_rules(query)
        return ""

    def add_error_lesson(self, query: str, bad_cypher: str, error_msg: str):
        """
        Store a procedural mistake in Cognee
        """
        if self.cognee:
            self.cognee.add_error_lesson(query, bad_cypher, error_msg)

    # -----------------------------
    # EPISODIC MEMORY - GRAPHITI
    # -----------------------------
    def add_episodic_interaction(
        self,
        question: str,
        final_cypher: str,
        result: str = None,
        errors: list = None,
        attempts: int = None,
    ):
        """
        Store a full interaction as ONE episode in Graphiti.
        Call this only at the end of execution (success or final failure).
        This wraps the async Graphiti call in a sync interface.
        """
        if not self.graphiti:
            return

        async def _run_graphiti():
            await self.graphiti.add_episode(
                question=question,
                final_cypher=final_cypher,
                result=result,
                errors=errors,
                attempts=attempts
            )

        try:
            print("[HybridMemoryManager] Sending episodic interaction to Graphiti...")
            asyncio.run(_run_graphiti())
        except Exception as e:
            print(f"[HybridMemoryManager] Failed to store episodic interaction: {e}")

    def search_episodic_memory(self, query: str) -> str:
        """
        Search past episodes in Graphiti using a synchronous wrapper.
        """
        if not self.graphiti:
            return ""
        
        async def _search():
            return await self.graphiti.search_memory(
                query=query, 
                group_id="cypher_agent_global"
            )
            
        try:
            return asyncio.run(_search())
        except Exception as e:
            print(f"[HybridMemoryManager] Episodic Search Error: {e}")
            return ""