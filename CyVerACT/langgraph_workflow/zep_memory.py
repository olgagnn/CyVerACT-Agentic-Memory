import os
from zep_cloud.client import Zep
from dotenv import load_dotenv, find_dotenv

# Loading env for sep api key 
load_dotenv(find_dotenv(), override=True)

class ZepMemoryWrapper:
    def __init__(self, user_id="cyver_agent_main"):
        api_key = os.getenv("ZEP_API_KEY")
        if not api_key:
            raise ValueError("ZEP_API_KEY missing from .env")
                
        print(f"[DEBUG] ZepWrapper initialized for User ID: '{user_id}'") # DEBUGGING :(
            
        self.client = Zep(api_key=api_key)
        self.user_id = user_id
        self._ensure_user()

    def _ensure_user(self):
        # Creating a new test user/updating existing 
        try:
            self.client.user.add(
                user_id=self.user_id,
                email="cyver_agent@ntua.gr",
                first_name="CyVer",
                last_name="Agent"
            )
        except Exception:
            pass # Moving on if user exists 

    # Adding procedural memory for the agent's mistakes 
    def add_error_lesson(self, user_query: str, bad_cypher: str, error_msg: str):
        lesson_text = (
            f"Rule derived from error: When answering about '{user_query}', "
            f"do NOT use the pattern found in '{bad_cypher}'. "
            f"Reason/Error: {error_msg}. "
            f"Correct approach: Verify schema labels and relationship directions."
        )
        
        print(f"[Zep] Learning new rule: {error_msg[:40]}...")
        try:
            self.client.graph.add(
                user_id=self.user_id,
                data=lesson_text,
                type="text"
            )
        except Exception as e:
            print(f"Zep Writes Error: {e}")

    # Getting rules via Zep Search, specifically looking into edges (facts)
    def get_relevant_rules(self, query: str) -> str:
        print(f"[Zep] Recalling rules for: {query}...")
        try:
            # Results is a GraphSearchResults object ! 
            results = self.client.graph.search(user_id=self.user_id, query=query)
            
            # If edges null 
            if not results or not getattr(results, 'edges', None):
                return ""
            
            formatted_rules = []
            
            # In Zep our facts (text) become -> Edges
            for edge in results.edges:
                # edge.fact has what we need 
                if hasattr(edge, 'fact'):
                    formatted_rules.append(f"- {edge.fact}")
            
            if not formatted_rules:
                return ""

            return "\n".join(formatted_rules)

        except Exception as e:
            print(f"Zep Search Error: {e}")
            return ""