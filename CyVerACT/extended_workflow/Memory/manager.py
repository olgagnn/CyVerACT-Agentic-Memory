import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

class MemoryManager:
    @staticmethod
    def get_memory_provider():
        # Get memory provider from .env file - default is ZEP :) 
        provider = os.getenv("MEMORY_PROVIDER", "zep").lower().strip()
        
        print(f"[System] Selected Memory Provider: {provider.upper()}")

        if provider == "zep":
            try:
                # Loading Zep Memory
                from Memory.zep_memory import ZepMemoryManager
                return ZepMemoryManager()
            except ImportError as e:
                print(f"ERROR: Cannot load Zep. Are you in the 'ZEP' Kernel?")
                print(f"Details: {e}")
                return None
        
        elif provider == "cognee":
            try:
                # Loading Cognee Memory
                from Memory.cognee_memory import CogneeMemoryManager
                return CogneeMemoryManager()
            except ImportError as e:
                print(f"ERROR: Cannot load Cognee. Are you in the 'COGNEE' Kernel?")
                print(f"Details: {e}")
                return None
            
        else:
            print(f"Unknown provider '{provider}'. Memory disabled.")
            return None