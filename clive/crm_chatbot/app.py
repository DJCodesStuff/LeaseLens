from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from models import CRERecord
from pydantic import ValidationError
import os
import pandas as pd
from google.genai import Client
import json
from user_data import UserDataManager
from datetime import datetime, timezone
import uuid
from vector_db_setup import VectorDatabaseManager
from qdrant_client.models import Filter
from agents import process_chat_message

load_dotenv()
app = Flask(__name__)
geminiClient = Client(api_key=os.getenv("GEMINI_API_KEY"))
model = geminiClient.models
modelName = 'gemini-2.5-flash'

client = MongoClient(os.getenv("MONGO_URI"))
db = client['CRM']
listings_col = db['Listings']
users_col = db['Users']
chat_col = db['chat_history']
session_col = db['sessions']

data_manager = UserDataManager(users_col=users_col, chat_col=chat_col, model=model, modelName=modelName)

# Initialize Vector Database Manager
try:
    vdb_manager = VectorDatabaseManager()
    print("✅ Vector Database Manager initialized successfully")
except Exception as e:
    print(f"❌ Error initializing Vector Database Manager: {e}")
    vdb_manager = None

@app.route('/chat', methods=['POST'])
def chat_with_bot():
    body = request.get_json()
    message = body.get("message")
    session_id = body.get("session_id")
    user_id = body.get("user_id", "anonymous")

    if not session_id:
        session_id = f"session_{datetime.now(timezone.utc).isoformat()}"

    # If user_id is provided in request, use it; otherwise try to get from session
    if user_id == "anonymous":
        session_record = session_col.find_one({"session_id": session_id})
        if session_record and session_record.get("user_id"):
            user_id = session_record["user_id"]
    else:
        # User_id was provided in request, update session collection
        session_col.update_one(
            {"session_id": session_id},
            {"$set": {"user_id": user_id, "created_at": datetime.utcnow().isoformat()}},
            upsert=True
        )

    if not message:
        return jsonify({"error": "Message is required"}), 400

    try:
        # Process message through agents
        result = process_chat_message(
            message=message,
            user_id=user_id,
            session_id=session_id,
            model=model,
            modelName=modelName,
            data_manager=data_manager,
            listings_col=listings_col,
            vdb_manager=vdb_manager
        )

        # Update user_id if it was changed during processing
        user_id = result["user_id"]

        # Store chat in MongoDB
        chat_entry = {
            "chat_id": str(uuid.uuid4()),
            "user_id": user_id,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "response": result["response"]
        }
        data_manager.add_chat_entry(chat_entry)
        
        # Add to vector database if available
        if vdb_manager:
            vdb_manager.add_document('chat_history', chat_entry, vdb_manager.create_chat_document)

        return jsonify({
            "response": result["response"],
            "session_id": session_id,
            "user_id": user_id
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === LISTINGS route (CSV + Pydantic) ===
@app.route('/upload_listings', methods=['POST'])
def upload_listings():
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': 'No file provided'}), 400

    try:
        df = pd.read_csv(file)
        validated, rejected = [], []

        for _, row in df.iterrows():
            try:
                record = CRERecord(
                    unique_id=row["unique_id"],
                    property_address=row["Property Address"],
                    floor=row["Floor"],
                    suite=row["Suite"],
                    size_sf=row["Size (SF)"],
                    rent_per_sf_year=row["Rent/SF/Year"],
                    broker_email=row["BROKER Email ID"],
                    annual_rent=row["Annual Rent"],
                    monthly_rent=row["Monthly Rent"],
                    gci_on_3_years=row["GCI On 3 Years"]
                )
                validated.append(record.dict())
            except ValidationError:
                rejected.append(row["unique_id"])

        if validated:
            listings_col.insert_many(validated)
            
            # Add to vector database if available
            if vdb_manager:
                for listing in validated:
                    vdb_manager.add_document('Listings', listing, vdb_manager.create_listing_document)

        return jsonify({
            'message': f'{len(validated)} records inserted',
            'rejected_record_ids': rejected
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# === USERS route (JSON input) ===
@app.route('/users', methods=['POST'])
def add_user():
    try:
        data = request.get_json()
        result = data_manager.create_user(data)
        
        # Add to vector database if available
        if vdb_manager and result['status'] == 'success':
            vdb_manager.add_document('Users', data, vdb_manager.create_user_document)
        
        status_code = 201 if result['status'] == 'success' else 400
        return jsonify(result), status_code
    except ValidationError as e:
        return jsonify({'error': e.errors()}), 400
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

# === CHAT_HISTORY route (GET conversations for a user) ===
@app.route('/crm/conversations/<user_id>', methods=['GET'])
def get_user_conversations(user_id):
    try:
        conversations = data_manager.get_chat_history(user_id)
        
        sessions = {}
        for chat in conversations:
            session_id = chat.get('session_id')
            if session_id not in sessions:
                sessions[session_id] = {
                    'session_id': session_id,
                    'user_id': user_id,
                    'conversations': []
                }
            sessions[session_id]['conversations'].append({
                'chat_id': chat.get('chat_id'),
                'timestamp': chat.get('timestamp'),
                'message': chat.get('message'),
                'response': chat.get('response')
            })
        
        sessions_list = list(sessions.values())
        sessions_list.sort(key=lambda x: x['conversations'][-1]['timestamp'] if x['conversations'] else '', reverse=True)
        
        return jsonify({
            'user_id': user_id,
            'total_sessions': len(sessions_list),
            'sessions': sessions_list
        }), 200
        
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

# === VECTOR DB SYNC endpoint ===
@app.route('/admin/sync-vector-db', methods=['POST'])
def sync_vector_database():
    """Admin endpoint to sync MongoDB data to Qdrant"""
    try:
        if not vdb_manager:
            return jsonify({'error': 'Vector database not available'}), 500
        
        vdb_manager.sync_mongodb_to_qdrant()
        return jsonify({'message': 'Vector database sync completed successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 