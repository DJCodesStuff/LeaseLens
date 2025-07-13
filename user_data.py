from pymongo.collection import Collection
from pydantic import ValidationError
from models import UserRecord, ChatRecord
from typing import Optional
from datetime import datetime
import json

class UserDataManager:
    def __init__(self, users_col: Collection, chat_col: Collection, model=None, modelName=None):
        self.users_col = users_col
        self.chat_col = chat_col
        self.model = model
        self.modelName = modelName

    def create_user(self, data: dict) -> dict:
        try:
            print("🔧 Creating user with data:", data)
            user = UserRecord(**data)
            print("✅ UserRecord created successfully:", user.dict())
            result = self.users_col.insert_one(user.dict())
            print("✅ User inserted into MongoDB with ID:", result.inserted_id)
            return {'status': 'success', 'message': 'User inserted'}
        except ValidationError as e:
            print("❌ Validation error:", e.errors())
            return {'status': 'error', 'message': 'Validation error', 'details': e.errors()}
        except Exception as ex:
            print("❌ Exception in create_user:", str(ex))
            return {'status': 'error', 'message': str(ex)}

    def update_user(self, email: str, updates: dict) -> dict:
        try:
            result = self.users_col.update_one({"email": email}, {"$set": updates})
            if result.modified_count > 0:
                return {'status': 'success', 'message': 'User updated'}
            return {'status': 'info', 'message': 'No user updated'}
        except Exception as ex:
            return {'status': 'error', 'message': str(ex)}

    def delete_user(self, email: str) -> dict:
        try:
            result = self.users_col.delete_one({"email": email})
            if result.deleted_count > 0:
                return {'status': 'success', 'message': 'User deleted'}
            return {'status': 'info', 'message': 'No user found with that email'}
        except Exception as ex:
            return {'status': 'error', 'message': str(ex)}

    def add_chat_entry(self, data: dict) -> dict:
        try:
            if "timestamp" not in data:
                data["timestamp"] = datetime.utcnow().isoformat()
            chat = ChatRecord(**data)
            self.chat_col.insert_one(chat.dict())
            return {'status': 'success', 'message': 'Chat inserted'}
        except ValidationError as e:
            return {'status': 'error', 'message': 'Validation error', 'details': e.errors()}
        except Exception as ex:
            return {'status': 'error', 'message': str(ex)}

    def get_chat_history(self, user_id: str, session_id: Optional[str] = None) -> list:
        query = {"user_id": user_id}
        if session_id:
            query["session_id"] = session_id
        return list(self.chat_col.find(query).sort("timestamp"))

    def extract_user_info(self, message: str) -> Optional[dict]:
        if not self.model or not self.modelName:
            print("❌ Model not available for user info extraction")
            return None
            
        prompt = (
            "Extract the user's contact information from the message below. "
            "Return the result as a JSON object with the following fields:\n\n"
            "- user_id (string, use the email as user_id)\n"
            "- name (string)\n"
            "- email (string)\n"
            "- role (string, default to 'user')\n\n"
            "Only return the JSON object. Do not include any explanation or commentary.\n\n"
            "Example:\n"
            "{\n"
            '  "user_id": "clivethe14@gmail.com",\n'
            '  "name": "Clive",\n'
            '  "email": "clivethe14@gmail.com",\n'
            '  "role": "user"\n'
            "}\n\n"
            f"User Message:\n{message}"
        )

        try:
            response = self.model.generate_content(model=self.modelName, contents=prompt)
            raw_output = response.text.strip()
            print("RAW USER EXTRACTION OUTPUT:", raw_output)

            if raw_output.startswith("```"):
                raw_output = raw_output.replace("```json", "").replace("```", "").strip()
            
            extracted = json.loads(raw_output)
            print("PARSED USER INFO:", extracted)
            return extracted
        except Exception as e:
            print("❌ Failed to extract user info:", e)
            return None 