import os
import requests
import json

class ZepMemoryHTTPS:
    def __init__(self, user_id="cyver_agent_main"):
        # URL for Zep Cloud instead of installing it because of dependency problem with cognee 
        self.base_url = "https://api.getzep.com/api/v2"
        self.api_key = os.getenv("ZEP_API_KEY")
        self.user_id = user_id
        
        if not self.api_key:
            print("[Zep] WARNING: ZEP_API_KEY is missing from .env")
            
        self.headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # User init for Zep
        self._ensure_user()

    def _ensure_user(self):
        """Making sure that user exists in Zep"""
        url = f"{self.base_url}/users"
        payload = {
            "user_id": self.user_id,
            "email": "cyver_agent@ntua.gr",
            "first_name": "CyVer",
            "last_name": "Agent"
        }
        try:
            # If user exists, pass
            requests.post(url, json=payload, headers=self.headers)
        except Exception:
            pass

    def search_memory(self, query: str, limit=3) -> str:
        """
        Reading from memory!
        Looking for facts (edges) in the graph
        Facts different for each user
        """
        if not self.api_key: return ""

        url = f"{self.base_url}/graph/search"
        payload = {
            "user_id": self.user_id,
            "query": query,
            "limit": limit
        }
        
        try:
            print(f"[Zep] Searching for: '{query}'...")
            response = requests.post(url, json=payload, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                edges = data.get('edges', [])
                
                if not edges:
                    return ""
                
                facts = []
                for edge in edges:
                    fact_text = edge.get('fact')
                    if fact_text:
                        facts.append(f"- {fact_text}")
                
                print(f"[Zep] Found {len(facts)} facts.")
                return "\n".join(facts)
            else:
                return ""
                
        except Exception as e:
            print(f"[Zep] Search Error: {e}")
            return ""

    def add_conversation_turn(self, session_id: str, user_query: str, ai_response: str):
        """
        Writing to memory! THIS IS OUR EPISODIC MEMORY !!!
        """
        if not self.api_key: return

        url = f"{self.base_url}/sessions/{session_id}/memory"
        
        payload = {
            "messages": [
                {
                    "role": "user", 
                    "role_type": "user", 
                    "content": user_query
                },
                {
                    "role": "assistant", 
                    "role_type": "assistant", 
                    "content": ai_response
                }
            ]
        }
        
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=5)
            if resp.status_code in [200, 201, 202]:
                print(f"[Zep] Memory saved for session: {session_id}")
            else:
                print(f"[Zep] Save failed: {resp.text}")
        except Exception as e:
            print(f"[Zep] Write Error: {e}")

    # --- ADDED: Method to retrieve recent chat history ---
    def get_chat_history(self, session_id: str, limit=10) -> str:
        """
        Retrieving recent chat history for context (e.g. 'that movie')
        """
        if not self.api_key: return ""
        
        url = f"{self.base_url}/sessions/{session_id}/memory"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                messages = data.get("messages", [])
                
                # Get the last N messages
                recent_messages = messages[-limit:]
                
                history_text = ""
                for msg in recent_messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    # Format: User: ... \n Assistant: ...
                    history_text += f"{role.capitalize()}: {content}\n"
                
                return history_text
            else:
                # If 404 (session not found yet), just return empty
                if response.status_code != 404:
                    print(f"[Zep] History Error: {response.text}")
                return ""
                
        except Exception as e:
            print(f"[Zep] Get History Error: {e}")
            return ""