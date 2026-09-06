import os
import asyncio
import nest_asyncio
from dotenv import load_dotenv, find_dotenv
from cognee.api.v1.search import SearchType
from Cognee_Graphiti_Memory.cognee_graph import CypherKnowledgeGraph

# Imports & Sync
nest_asyncio.apply()
load_dotenv(find_dotenv(), override=True)

# Paths 
root_path = os.path.abspath(".cognee_data").replace("\\", "/")
os.makedirs(root_path, exist_ok=True)

# Importing cognee AFTER setting env vars
import cognee
from cognee.modules.engine.operations.setup import setup as internal_setup

CUSTOM_PROMPT = """
You MUST extract ALL of the following entities:

1. CypherErrorType:
- name

2. CypherError:
- name
- description
- is_type → CypherErrorType

3. FixRule:
- description
- fixes → CypherError

4. QueryExample:
- user_query
- bad_cypher
- error_message
- related_error → CypherError

Rules:
- ALWAYS create a FixRule
- ALWAYS create a QueryExample
- FixRule must be general and reusable
- QueryExample must contain exact values

Relationships:
- FixRule fixes CypherError
- QueryExample relates to CypherError

Output MUST include all entity types.
"""

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
        lesson_text = f"""
            Cypher Error Type: {error_msg.split(':')[0]}

            Cypher Error:
            - Name: {error_msg}
            - Description: The agent attempted to execute invalid Cypher against the Neo4j database.

            Fix Rule:
            - Description: Analyze the following error and create a single, highly specific, and reusable Cypher rule to prevent it in the future. 
            Error Context to analyze: '{error_msg}'. 
            Do NOT just copy the error. Write a definitive rule (e.g., 'Always use WITH before COUNT', 'Reverse the relationship arrow for ACTED_IN').

            Query Example:
            - User Query: {user_query}
            - Bad Cypher: {bad_cypher}
            - Error Message: {error_msg}
            """
        print(f"[Cognee] Learning lesson...")
        async def _process():
            await cognee.add(lesson_text, dataset_name="cyver_error_log")
            await cognee.cognify(
                graph_model=CypherKnowledgeGraph,
                custom_prompt=CUSTOM_PROMPT
            )
        try:
            asyncio.run(_process())
            print("[Cognee] Memory Updated!")
        except Exception as e:
            print(f"[Cognee Write Error]: {e}")

    def get_relevant_rules(self, query: str) -> str:
        print(f"[Cognee] Searching rules for: {query}...")
        async def _search():
            return await cognee.search(
                query_text=f"""
                Cypher query debugging rules.

                User request:
                {query}

                STRICT INSTRUCTIONS:
                - Return ONLY the most relevant rules
                - If Cognee memory is empty, return ONLY the phrase 'No results'
                - Maximum length: 200 words
                - Prefer concise bullet points
                - DO NOT repeat similar rules
                - DO NOT include long explanations
                - DO NOT include full examples unless critical

                Focus on:
                - aggregation mistakes (WITH, COUNT)
                - relationship direction
                - schema issues (labels, properties)
                - duplicate results (DISTINCT)
                """,
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