import os

# Import Cognee 
try:
    from Memory.cognee_memory import CogneeMemoryManager
    COGNEE_AVAILABLE = True
except ImportError:
    COGNEE_AVAILABLE = False
    print("[Hybrid Memory Manager] Cognee not found.")

# Import Zep (BUT with HTTP Client)
try:
    from Memory.zep_memory_https import ZepMemoryHTTPS
    ZEP_AVAILABLE = True
except ImportError:
    ZEP_AVAILABLE = False
    print("[Hybrid Memory Manager] Zep HTTP client not found.")

class HybridMemoryManager:
    def __init__(self):
        self.cognee = None
        self.zep = None
        
        # Init Cognee - OUR SEMANTIC MEMORY !!!!
        if COGNEE_AVAILABLE:
            try:
                self.cognee = CogneeMemoryManager()
            except Exception as e:
                print(f"[Hybrid Memory Manager] Cognee Init Failed: {e}")

        # Init Zep OUR EPISODIC MEMORY !!!!
        if ZEP_AVAILABLE and os.getenv("ZEP_API_KEY"):
            try:
                # Using user_id = cyver_agent_main, ALWAYS delete user to delete the relative data 
                self.zep = ZepMemoryHTTPS(user_id="cyver_agent_main")
                print("[Hybrid Memory Manager] Zep HTTP Connected.")
            except Exception as e:
                print(f"[Hybrid Memory Manager] Zep Init Failed: {e}")

    def get_relevant_context(self, query: str, thread_id: str = None) -> str:
        """Retrieves from both our memories!"""
        context_parts = []
        
        # Semantic Memory - Rules from Cognee 
        if self.cognee:
            rules = self.cognee.get_relevant_rules(query)
            if rules:
                context_parts.append(f" TECHNICAL CONSTRAINTS & RULES (To follow strictly):\n{rules}")
        
        # Episodic Memory - Chat History from Zep
        if self.zep:
            try:
                # Semantic Search (Facts)
                facts = self.zep.search_memory(query)
                if facts:
                    context_parts.append(f" RELEVANT FACTS:\n{facts}")
                
                # RECENT CHAT HISTORY 
                if thread_id:
                    # 3 last messages from that thread - can change the number later
                    history = self.zep.get_chat_history(thread_id=thread_id, limit=3)
                    if history:
                         context_parts.append(f" RECENT CONVERSATION HISTORY:\n{history}")
            except Exception as e:
                print(f"[Hybrid Manager] Zep Error: {e}")

        return "\n\n".join(context_parts)
    
    def get_procedural_lessons(self, query: str) -> str:
        if self.cognee:
            return self.cognee.get_relevant_rules(query)
        return ""

    def add_error_lesson(self, query, bad_cypher, error_msg):
        """Adding a lesson of a mistake"""
        if self.cognee:
            self.cognee.add_error_lesson(query, bad_cypher, error_msg)