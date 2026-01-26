import os
from zep_cloud.client import Zep
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

api_key = os.getenv("ZEP_API_KEY")
client = Zep(api_key=api_key)

# DELETING USERS FOR TESTING 
users_to_delete = ["cyver_agent_test", "cyver_agent_main"]

print("Starting Memory Cleanup...")

for user_id in users_to_delete:
    try:
        print(f"Attempting to delete user: {user_id}...")
        client.user.delete(user_id)
        print(f"User '{user_id}' and all their memories deleted.")
    except Exception as e:
        print(f"Could not delete '{user_id}' (maybe didn't exist): {e}")

print("------------------------------------------------")
print("Memory is clean.")