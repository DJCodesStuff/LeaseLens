import requests
import json

BASE_URL = "http://localhost:5000"

# Sample payload for /chat endpoint
data = {
    "message": "Who handled the lease with the highest rent and what is the broker's name?",
    "user_id": "khaleesi@dragonstone.com",
    # session_id is optional; if omitted, the server will generate one
}

response = requests.post(f"{BASE_URL}/chat", json=data)

print("Status Code:", response.status_code)
try:
    print("Response JSON:", json.dumps(response.json(), indent=2))
except Exception:
    print("Response Text:", response.text) 