# test_env.py
from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env from the *current* directory
env_path = Path(__file__).parent.parent / ".env"
loaded = load_dotenv(env_path)

print(f"load_dotenv returned: {loaded}")  # True if file found & parsed

# Show values (None if not loaded)
print("GOOGLE_API_KEY =", os.getenv("GEMINI_API_KEY"))
print("MODEL_NAME     =", os.getenv("MODEL_NAME"))
