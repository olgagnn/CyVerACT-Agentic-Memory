import os
from dotenv import load_dotenv, find_dotenv

# Loading Zep Memory
from memory.zep_memory import ZepMemoryManager

# Loading Cognee Memory 
# from backend.memory.cognee_store import CogneeMemoryManager

load_dotenv(find_dotenv(), override=True)

class MemoryManager:
    @staticmethod
    def get_memory_provider():
        # Get memory provider from .env file - default is ZEP :) 
        provider = os.getenv("MEMORY_PROVIDER", "zep").lower().strip()
        
        print(f"🔄 [System] Selected Memory Provider: {provider.upper()}")

        if provider == "zep":
            return ZepMemoryManager()
        
        elif provider == "cognee":
            # return CogneeMemoryManager() # for later implementation 
            print("Cognee not implemented yet. Returning None.")
            return None
            
        else:
            print(f"Unknown provider '{provider}'. Memory disabled.")
            return None