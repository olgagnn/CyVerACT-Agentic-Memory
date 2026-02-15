import os
import requests
from dotenv import load_dotenv, find_dotenv

# Loading env
load_dotenv(find_dotenv(), override=True)

base_url = "https://api.getzep.com/api/v2"
api_key = os.getenv("ZEP_API_KEY")

if not api_key:
    print("ERROR: ZEP_API_KEY missing.")
    exit()

headers = {
    "Authorization": f"Api-Key {api_key}",
    "Content-Type": "application/json"
}

def get_all_users():
    try:
        response = requests.get(f"{base_url}/users?page_size=100", headers=headers)
        if response.status_code == 200:
            data = response.json()
            
            # Διόρθωση: Έλεγχος αν είναι ήδη λίστα
            if isinstance(data, list):
                users = data
            elif isinstance(data, dict):
                users = data.get("users", [])
            else:
                users = []
                
            return users
        else:
            print(f"Could not list users: {response.text}")
            return []
    except Exception as e:
        print(f"Connection Error: {e}")
        return []

def delete_user(user_id):
    try:
        response = requests.delete(f"{base_url}/users/{user_id}", headers=headers)
        if response.status_code in [200, 204]:
            print(f"Deleted: {user_id}")
        else:
            print(f"Failed to delete {user_id}: {response.text}")
    except Exception as e:
        print(f"Error deleting {user_id}: {e}")

# --- MAIN EXECUTION ---
print("-------------------- ZEP TOTAL WIPE STARTED --------------------")

current_users = get_all_users()

if not current_users:
    print("Zep is already EMPTY. No users found.")
else:
    print(f"Found {len(current_users)} users. Deleting them now...")
    for user in current_users:
        u_id = user.get("user_id")
        if u_id:
            delete_user(u_id)
            
    # Checking if everythin's good 
    print("Verifying...")
    remaining = get_all_users()
    if not remaining:
        print("SUCCESS: All users verified deleted.")
    else:
        print(f"Warning: {len(remaining)} users still remain.")