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
             
            # # With this I resolved DatabaseNotCreatedError!!!
            # try:
            #     await internal_setup()
            # except Exception as e:
            #     print(f"[Cognee Setup Note]: {e}")

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
            await cognee.add(lesson_text, dataset_name="cyver_error_log")
            await cognee.cognify()
        try:
            asyncio.run(_process())
            print("[Cognee] Memory Updated!")
        except Exception as e:
            print(f"[Cognee Write Error]: {e}")

    def get_relevant_rules(self, query: str) -> str:
        print(f"[Cognee] Searching rules for: {query}...")
        async def _search():
            return await cognee.search(
                query_text=query,
                query_type=cognee.SearchType.GRAPH_COMPLETION,
            )
        try:
            results = asyncio.run(_search())
            if not results:
                print("[Cognee] No results found.")
                return ""

            formatted = []
            for r in results:
                if isinstance(r, str):
                    content = r.strip()
                else:
                    content = getattr(r, 'text', getattr(r, 'content', str(r))).strip()
                if content and len(content) > 10:
                    formatted.append(f"- {content}")

            if not formatted:
                print("[Cognee] No meaningful results found.")
                return ""

            print(f"[Cognee] Found {len(formatted)} rules.")
            for i, rule in enumerate(formatted, 1):
                print(f" Rule {i}: {rule}")

            return "\n".join(formatted)
        except Exception as e:
            print(f"[Cognee Read Error]: {e}")
            return ""