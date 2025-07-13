# CRM Chatbot with RAG (Retrieval-Augmented Generation)

A commercial real estate chatbot system built with Flask, MongoDB, Google Gemini AI, and Qdrant vector database for intelligent conversation and property search.

## 🚀 Features

- **Multi-Agentic Conversational AI**: Modular agents for intent classification, user info extraction, property search, and advanced graph queries
- **RAG System**: Retrieval-Augmented Generation with Qdrant vector database (CSV, PDF, TXT, JSON ingestion)
- **User Management**: Automatic user creation, profile management, and CRUD operations
- **Session Tagging**: Each conversation session is tagged as `Inquiring`, `Unresolved`, or `Resolved` for easy tracking
- **Property Search**: Advanced listing search with fuzzy matching and semantic retrieval
- **Conversation Memory**: Persistent chat history across sessions, accessible via API
- **Intent Classification**: Smart message classification for different actions
- **Vector Search**: Semantic search across users, chat history, and listings
- **Advanced Graph Agent**: (See `DHRUV/Agents/graph_query_agent.py`) for complex analytics

## 📋 Prerequisites

- Python 3.8+
- Docker (for Qdrant)
- MongoDB (local or cloud)
- Google Gemini API key

## 🛠️ Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd crm_chatbot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the root directory:

```env
# MongoDB Configuration
MONGO_URI=mongodb://localhost:27017/CRM

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Qdrant Configuration (optional, defaults to localhost:6333)
QDRANT_URL=http://localhost:6333
```

### 3. Start Qdrant (Vector Database)

```bash
# Start Qdrant using Docker
docker run -p 6333:6333 qdrant/qdrant
```

### 4. Setup Vector Database

```bash
python vector_db_setup.py
```

### 5. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 📁 Project Structure

```
crm_chatbot/
├── app.py                 # Main Flask application
├── models.py              # Pydantic models for data validation
├── user_data.py           # User data management utilities
├── vector_db_setup.py     # Qdrant vector database setup
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── API_CONTRACT.md        # Full API contract and sample requests
├── ARCHITECTURE.md        # System and data flow diagrams
└── README.md              # This file
```

## 🔧 API Endpoints

All endpoints return JSON with `status` and `processing_time` fields. See `API_CONTRACT.md` for full details.

### Chat & RAG

**POST `/chat`**
- Send a message to the chatbot and receive a response (RAG-enabled).
- Request: `{ "message": "Show me offices in downtown.", "user_id": "user1@example.com", "session_id": "session_2024-07-13T12:00:00Z" }`
- Response: `{ "status": "success", "response": "...", "session_id": "...", "user_id": "...", "processing_time": 0.12 }`

### Document Ingestion

**POST `/upload_docs`**
- Upload property listings in CSV, JSON, TXT, or PDF format.
- Form Data: `file` (one or more files)
- Response: See `API_CONTRACT.md` for details.

**POST `/upload_listings`**
- Alias for `/upload_docs` (for backward compatibility)

### User Management (CRM)

**POST `/users`**
- Create a new user.

**POST `/crm/create_user`**
- Alias for user creation.

**GET `/crm/get_user/<user_id>`**
- Get user info by user_id.

**PUT `/crm/update_user/<user_id>`**
- Update user info.

**DELETE `/crm/delete_user/<user_id>`**
- Delete a user.

### Conversation & Session Management

**GET `/crm/conversations/<user_id>`**
- Get all conversation sessions for a user, grouped by session. Each session has a `status` (see below).

**POST `/crm/resolve_session/<session_id>`**
- Mark a session as resolved.

**POST `/reset`**
- Delete all chat history (global or for a specific user).

### Admin

**POST `/admin/sync-vector-db`**
- Manually sync MongoDB data to Qdrant (vector DB).

---

## 🗂️ Data Models

**UserRecord**
```json
{
  "user_id": "user1@example.com",
  "name": "User One",
  "email": "user1@example.com",
  "role": "user"
}
```

**ChatRecord**
```json
{
  "chat_id": "...",
  "user_id": "user1@example.com",
  "session_id": "session_2024-07-13T12:00:00Z",
  "timestamp": "2024-07-13T12:00:00Z",
  "message": "...",
  "response": "..."
}
```

**CRERecord (Listing)**
```json
{
  "unique_id": 1,
  "property_address": "123 Main St",
  "floor": "5",
  "suite": "501",
  "size_sf": 2000,
  "rent_per_sf_year": 50.0,
  "broker_email": "broker1@example.com",
  "annual_rent": 100000,
  "monthly_rent": 8333.33,
  "gci_on_3_years": 25000
}
```

## 🏷️ Session Tagging & Categorization

- Each conversation session is tagged with a `status`:
  - `Inquiring`: User is actively searching or asking about properties
  - `Unresolved`: Session started but not yet resolved
  - `Resolved`: Session marked as completed (via `/crm/resolve_session/<session_id>`)
- Status is updated automatically based on detected intent or via API.

## 🧪 Sample Conversation Log

```json
[
  {
    "chat_id": "1",
    "user_id": "sarah@test.com",
    "session_id": "session_2024-07-13T12:00:00Z",
    "timestamp": "2024-07-13T12:00:00Z",
    "message": "Hi, I am Sarah Johnson, my email is sarah@test.com. I am looking for office space in downtown.",
    "response": "Thanks! I've saved your info to our CRM."
  },
  {
    "chat_id": "2",
    "user_id": "sarah@test.com",
    "session_id": "session_2024-07-13T12:00:00Z",
    "timestamp": "2024-07-13T12:01:00Z",
    "message": "Show me properties under $5000/month",
    "response": "Here are some matches: 123 Main St - $4500/mo, 456 Broadway - $4800/mo"
  }
]
```

## 🏗️ Architecture & Multi-Agent System

- See `ARCHITECTURE.md` for a full system diagram and component breakdown.
- Multi-agentic logic is implemented in `agents.py` and `DHRUV/Agents/`.
- Advanced analytics and graph queries are supported via `DHRUV/Agents/graph_query_agent.py`.

## 📄 API Contract

- See `API_CONTRACT.md` for full endpoint details, request/response schemas, and sample calls.

## 📅 Calendar Integration (Optional)

- To integrate calendar events, you could:
  - Add endpoints for event creation, update, and retrieval (e.g., `/crm/calendar_events`)
  - Store event data in MongoDB, linked to user/session
  - Use intent classification to detect scheduling requests
  - (Optionally) Integrate with Google Calendar API for real-time sync

## 🔒 Security Notes

- Store API keys securely in environment variables
- Use HTTPS in production
- Implement proper authentication for admin endpoints
- Regular backups of MongoDB and Qdrant data

## 📈 Performance Optimization

- Qdrant collections are optimized for cosine similarity search
- Embeddings use all-MiniLM-L6-v2 model (384 dimensions)
- Chat history is limited to recent conversations in RAG context
- Vector database sync happens automatically for new data

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 