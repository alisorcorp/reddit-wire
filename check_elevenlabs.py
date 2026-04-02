import requests
import os
from dotenv import load_dotenv

load_dotenv()

def check_balance():
    api_key = os.getenv("ELEVENLABS_API_KEY")
    url = "https://api.elevenlabs.io/v1/user/subscription"
    headers = {"xi-api-key": api_key}
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        print(f"Character count: {data['character_count']}")
        print(f"Character limit: {data['character_limit']}")
        print(f"Remaining: {data['character_limit'] - data['character_count']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    check_balance()
