import os
import asyncio
import nest_asyncio
from dotenv import load_dotenv, find_dotenv

# Imports & Sync
nest_asyncio.apply()
load_dotenv(find_dotenv(), override=True)

# Paths 
root_path = os.path.abspath(".cognee_data").replace("\\", "/")
os.makedirs(root_path, exist_ok=True)

# Environment Variables 
os.environ["COGNEE_ROOT_DIR"] = root_path 
os.environ["DB_PROVIDER"] = "sqlite"
os.environ["DB_NAME"] = "cognee_db"
os.environ["VECTOR_DB_PROVIDER"] = "lancedb"
os.environ["LLM_PROVIDER"] = "openai"
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"

# I'll use kuzu for cognee's graph storage cause it's easier and more practical 
#os.environ["GRAPH_DATABASE_PROVIDER"] = "kuzu"

os.environ["GRAPH_DATABASE_PROVIDER"] = "neo4j"
os.environ["GRAPH_DATABASE_URL"] = os.getenv("NEO4J_URI")
os.environ["GRAPH_DATABASE_USERNAME"] = os.getenv("NEO4J_USERNAME")
os.environ["GRAPH_DATABASE_PASSWORD"] = os.getenv("NEO4J_PASSWORD")

# Importing cognee AFTER setting env vars
import cognee
from cognee.modules.engine.operations.setup import setup as internal_setup

class CogneeMemoryManager:
    def __init__(self, reset_db=False):
        print(f"[Cognee] Initializing Memory at: {root_path}")
        
        async def _init():
            if reset_db:
                print("[Cognee] Manual Reset: Pruning data...")
                await cognee.prune.prune_data()
                await cognee.prune.prune_system(metadata=True)
             
            # With this I resolved DatabaseNotCreatedError!!!
            try:
                await internal_setup()
            except Exception as e:
                print(f"[Cognee Setup Note]: {e}")

        try:
            asyncio.run(_init())
            print("[Cognee] Ready !")
        except Exception as e:
            print(f"[Cognee Init Error]: {e}")

    def add_error_lesson(self, user_query: str, bad_cypher: str, error_msg: str):
        lesson_text = (
            f"Constraint Violation Log for query '{user_query}'. "
            f"Incorrect Cypher: '{bad_cypher}'. "
            f"Error: {error_msg}. Rule: Do not use this pattern again."
        )
        print(f"[Cognee] Learning lesson...")
        async def _process():
            await cognee.add(lesson_text, "CyVer_Error_Log")
            await cognee.cognify()
        try:
            asyncio.run(_process())
            print("[Cognee] Memory Updated!")
        except Exception as e:
            print(f"[Cognee Write Error]: {e}")

    def get_relevant_rules(self, query: str) -> str:
        print(f"[Cognee] Searching rules for: {query}...")
        async def _search():
            return await cognee.search(query_text=query)
        try:
            results = asyncio.run(_search())
            if not results: 
                print("[Cognee] No results found.")
                return ""
            # Formatting 
            formatted = []
            for r in results:
                content = getattr(r, 'text', getattr(r, 'content', str(r)))
                formatted.append(f"- {content}")
            print(f"[Cognee] Found {len(formatted)} rules.")
            return "\n".join(formatted)
        except Exception as e:
            print(f"[Cognee Read Error]: {e}")
            return ""