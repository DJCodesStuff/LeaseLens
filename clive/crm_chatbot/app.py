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
import time
import io
import json
import pandas as pd
from werkzeug.utils import secure_filename
import pdfplumber

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
    start_time = time.time()
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
        return jsonify({"status": "error", "error": "Message is required", "processing_time": round(time.time() - start_time, 4)}), 400

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

        # === SESSION STATUS LOGIC ===
        # Get current session
        session_doc = session_col.find_one({"session_id": session_id})
        current_status = session_doc.get("status", "Unresolved") if session_doc else "Unresolved"
        # If not resolved, update status based on intent
        if current_status != "Resolved":
            intents = result.get("intents") or []
            new_status = current_status
            if "listings_request" in intents:
                new_status = "Inquiring"
            else:
                new_status = current_status or "Unresolved"
            session_col.update_one(
                {"session_id": session_id},
                {"$set": {"status": new_status}},
                upsert=True
            )

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

        response = {
            "status": "success",
            "response": result["response"],
            "session_id": session_id,
            "user_id": user_id,
            "processing_time": round(time.time() - start_time, 4)
        }
        # Optionally include RAG context info if present
        if "rag_context" in result:
            response["rag_context"] = result["rag_context"]
        return jsonify(response)

    except Exception as e:
        return jsonify({"status": "error", "error": str(e), "processing_time": round(time.time() - start_time, 4)}), 500

# === DOCUMENT INGESTION route (CSV, PDF, TXT, JSON) ===
@app.route('/upload_docs', methods=['POST'])
def upload_documents():
    start_time = time.time()
    files = request.files.getlist('file')
    if not files:
        return jsonify({'status': 'error', 'error': 'No files provided', 'processing_time': round(time.time() - start_time, 4)}), 400

    results = []
    total_time = 0

    def detect_file_type(filename):
        ext = filename.lower().split('.')[-1]
        if ext == 'csv':
            return 'csv'
        elif ext == 'pdf':
            return 'pdf'
        elif ext == 'txt':
            return 'txt'
        elif ext == 'json':
            return 'json'
        else:
            return 'unknown'

    cre_fields = [
        'unique_id', 'property_address', 'floor', 'suite', 'size_sf',
        'rent_per_sf_year', 'broker_email', 'annual_rent', 'monthly_rent', 'gci_on_3_years'
    ]

    def parse_txt_line(line):
        # Expects comma-separated values in CRERecord order
        parts = [p.strip() for p in line.split(',')]
        if len(parts) != len(cre_fields):
            return None
        try:
            record = CRERecord(
                unique_id=int(parts[0]),
                property_address=parts[1],
                floor=parts[2],
                suite=parts[3],
                size_sf=int(parts[4]),
                rent_per_sf_year=float(parts[5]),
                broker_email=parts[6],
                annual_rent=float(parts[7]),
                monthly_rent=float(parts[8]),
                gci_on_3_years=float(parts[9])
            )
            return record.model_dump()
        except Exception:
            return None

    for file in files:
        start_time_file = time.time()
        filename = secure_filename(file.filename)
        file_type = detect_file_type(filename)
        result = {
            'filename': filename,
            'type': file_type,
            'records_inserted': 0,
            'rejected_records': 0,
            'errors': [],
            'processing_time': 0.0
        }
        try:
            if file_type == 'csv':
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
                        validated.append(record.model_dump())
                    except ValidationError as ve:
                        rejected.append(str(ve))
                if validated:
                    listings_col.insert_many(validated)
                    if vdb_manager:
                        for listing in validated:
                            vdb_manager.add_document('Listings', listing, vdb_manager.create_listing_document)
                result['records_inserted'] = len(validated)
                result['rejected_records'] = len(rejected)
                result['errors'] = rejected
            elif file_type == 'json':
                content = json.load(file)
                if isinstance(content, list):
                    validated, rejected = [], []
                    for item in content:
                        try:
                            record = CRERecord(**item)
                            validated.append(record.model_dump())
                        except ValidationError as ve:
                            rejected.append(str(ve))
                    if validated:
                        listings_col.insert_many(validated)
                        if vdb_manager:
                            for listing in validated:
                                vdb_manager.add_document('Listings', listing, vdb_manager.create_listing_document)
                    result['records_inserted'] = len(validated)
                    result['rejected_records'] = len(rejected)
                    result['errors'] = rejected
                else:
                    result['errors'] = ['JSON must be a list of objects matching the CRERecord schema.']
            elif file_type == 'txt':
                lines = file.read().decode('utf-8').splitlines()
                validated, rejected = [], []
                for line in lines:
                    rec = parse_txt_line(line)
                    if rec:
                        validated.append(rec)
                    else:
                        rejected.append(f'Invalid line: {line}')
                if validated:
                    listings_col.insert_many(validated)
                    if vdb_manager:
                        for listing in validated:
                            vdb_manager.add_document('Listings', listing, vdb_manager.create_listing_document)
                result['records_inserted'] = len(validated)
                result['rejected_records'] = len(rejected)
                result['errors'] = rejected
            elif file_type == 'pdf':
                validated, rejected = [], []
                with pdfplumber.open(file) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if not text:
                            continue
                        for line in text.split('\n'):
                            rec = parse_txt_line(line)
                            if rec:
                                validated.append(rec)
                            else:
                                rejected.append(f'Invalid line: {line}')
                if validated:
                    listings_col.insert_many(validated)
                    if vdb_manager:
                        for listing in validated:
                            vdb_manager.add_document('Listings', listing, vdb_manager.create_listing_document)
                result['records_inserted'] = len(validated)
                result['rejected_records'] = len(rejected)
                result['errors'] = rejected
            else:
                result['errors'] = [f'Unsupported file type: {file_type}']
        except Exception as e:
            result['errors'] = [str(e)]
        result['processing_time'] = round(time.time() - start_time_file, 3)
        total_time += result['processing_time']
        results.append(result)

    return jsonify({
        'status': 'success',
        'message': 'Documents processed successfully',
        'processed_files': results,
        'total_processing_time': total_time,
        'vector_db_updated': bool(vdb_manager),
        'processing_time': round(time.time() - start_time, 4)
    })

# === Backward compatibility: /upload_listings redirects to /upload_docs ===
@app.route('/upload_listings', methods=['POST'])
def upload_listings():
    return upload_documents()

# === USERS route (JSON input) ===
@app.route('/users', methods=['POST'])
def add_user():
    start_time = time.time()
    try:
        data = request.get_json()
        result = data_manager.create_user(data)
        
        # Add to vector database if available
        if vdb_manager and result['status'] == 'success':
            vdb_manager.add_document('Users', data, vdb_manager.create_user_document)
        
        status_code = 201 if result['status'] == 'success' else 400
        return jsonify({**result, 'processing_time': round(time.time() - start_time, 4)}), status_code
    except ValidationError as e:
        return jsonify({'status': 'error', 'error': e.errors(), 'processing_time': round(time.time() - start_time, 4)}), 400
    except Exception as ex:
        return jsonify({'status': 'error', 'error': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# === USER CRUD ENDPOINTS ===

# Alias for user creation (already exists as /users)
@app.route('/crm/create_user', methods=['POST'])
def crm_create_user():
    return add_user()

# Update user info by user_id
@app.route('/crm/update_user/<user_id>', methods=['PUT'])
def crm_update_user(user_id):
    start_time = time.time()
    try:
        updates = request.get_json()
        if not updates:
            return jsonify({'status': 'error', 'error': 'No update data provided', 'processing_time': round(time.time() - start_time, 4)}), 400
        result = data_manager.update_user(user_id, updates)
        return jsonify({**result, 'processing_time': round(time.time() - start_time, 4)}), 200 if result['status'] == 'success' else 400
    except Exception as ex:
        return jsonify({'status': 'error', 'error': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# Delete user by user_id
@app.route('/crm/delete_user/<user_id>', methods=['DELETE'])
def crm_delete_user(user_id):
    start_time = time.time()
    try:
        result = data_manager.delete_user(user_id)
        return jsonify({**result, 'processing_time': round(time.time() - start_time, 4)}), 200 if result['status'] == 'success' else 400
    except Exception as ex:
        return jsonify({'status': 'error', 'error': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# Get user info by user_id
@app.route('/crm/get_user/<user_id>', methods=['GET'])
def crm_get_user(user_id):
    start_time = time.time()
    try:
        user = users_col.find_one({'user_id': user_id}, {'_id': 0})
        if user:
            return jsonify({'status': 'success', 'user': user, 'processing_time': round(time.time() - start_time, 4)}), 200
        else:
            return jsonify({'status': 'error', 'message': 'User not found', 'processing_time': round(time.time() - start_time, 4)}), 404
    except Exception as ex:
        return jsonify({'status': 'error', 'error': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# === RESOLVE SESSION ENDPOINT ===
@app.route('/crm/resolve_session/<session_id>', methods=['POST'])
def resolve_session(session_id):
    start_time = time.time()
    try:
        result = session_col.update_one(
            {"session_id": session_id},
            {"$set": {"status": "Resolved"}}
        )
        if result.matched_count:
            return jsonify({
                'status': 'success',
                'message': f'Session {session_id} marked as Resolved.',
                'processing_time': round(time.time() - start_time, 4)
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': f'Session {session_id} not found.',
                'processing_time': round(time.time() - start_time, 4)
            }), 404
    except Exception as ex:
        return jsonify({'status': 'error', 'message': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# === CHAT_HISTORY route (GET conversations for a user) ===
@app.route('/crm/conversations/<user_id>', methods=['GET'])
def get_user_conversations(user_id):
    start_time = time.time()
    try:
        conversations = data_manager.get_chat_history(user_id)
        sessions = {}
        for chat in conversations:
            session_id = chat.get('session_id')
            if session_id not in sessions:
                # Fetch session status
                session_doc = session_col.find_one({"session_id": session_id})
                session_status = session_doc.get("status", "Unresolved") if session_doc else "Unresolved"
                sessions[session_id] = {
                    'session_id': session_id,
                    'user_id': user_id,
                    'status': session_status,
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
            'status': 'success',
            'user_id': user_id,
            'total_sessions': len(sessions_list),
            'sessions': sessions_list,
            'processing_time': round(time.time() - start_time, 4)
        }), 200
    except Exception as ex:
        return jsonify({'status': 'error', 'error': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# === CONVERSATION RESET ENDPOINT ===
@app.route('/reset', methods=['POST'])
def reset_conversation():
    start_time = time.time()
    try:
        data = request.get_json(silent=True) or {}
        user_id = data.get('user_id')
        if user_id:
            result = chat_col.delete_many({'user_id': user_id})
            return jsonify({
                'status': 'success',
                'message': f'All chat history for user {user_id} deleted.',
                'deleted_count': result.deleted_count,
                'processing_time': round(time.time() - start_time, 4)
            }), 200
        else:
            result = chat_col.delete_many({})
            return jsonify({
                'status': 'success',
                'message': 'All chat history deleted.',
                'deleted_count': result.deleted_count,
                'processing_time': round(time.time() - start_time, 4)
            }), 200
    except Exception as ex:
        return jsonify({'status': 'error', 'message': str(ex), 'processing_time': round(time.time() - start_time, 4)}), 500

# === VECTOR DB SYNC endpoint ===
@app.route('/admin/sync-vector-db', methods=['POST'])
def sync_vector_database():
    start_time = time.time()
    """Admin endpoint to sync MongoDB data to Qdrant"""
    try:
        if not vdb_manager:
            return jsonify({'status': 'error', 'error': 'Vector database not available', 'processing_time': round(time.time() - start_time, 4)}), 500
        
        vdb_manager.sync_mongodb_to_qdrant()
        return jsonify({'status': 'success', 'message': 'Vector database sync completed successfully', 'processing_time': round(time.time() - start_time, 4)}), 200
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e), 'processing_time': round(time.time() - start_time, 4)}), 500

if __name__ == '__main__':
    app.run(debug=True) 