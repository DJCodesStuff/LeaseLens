# CRM Chatbot with RAG (Retrieval-Augmented Generation)

A commercial real estate chatbot system built with Flask, MongoDB, Google Gemini AI, and Qdrant vector database for intelligent conversation and property search.

## 🚀 Features

- **Intelligent Chatbot**: Powered by Google Gemini AI
- **RAG System**: Retrieval-Augmented Generation with Qdrant vector database
- **User Management**: Automatic user creation and profile management
- **Property Search**: Advanced listing search with fuzzy matching
- **Conversation Memory**: Persistent chat history across sessions
- **Intent Classification**: Smart message classification for different actions
- **Vector Search**: Semantic search across users, chat history, and listings

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

# Or download and run Qdrant binary
# Visit: https://qdrant.tech/documentation/guides/installation/
```

### 4. Setup Vector Database

```bash
# Initialize and sync vector database
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
└── README.md             # This file
```

## 🔧 API Endpoints

### Chat Endpoint
```http
POST /chat
Content-Type: application/json

{
  "message": "Hi, I'm John Doe, john@example.com. I'm looking for office space in downtown.",
  "user_id": "john@example.com"  // Optional
}
```

### User Management
```http
POST /users
Content-Type: application/json

{
  "user_id": "john@example.com",
  "name": "John Doe",
  "email": "john@example.com",
  "role": "user"
}
```

### Upload Listings
```http
POST /upload_listings
Content-Type: multipart/form-data

file: listings.csv
```

### Get User Conversations
```http
GET /crm/conversations/{user_id}
```

### Sync Vector Database
```http
POST /admin/sync-vector-db
```

## 🧪 Testing

### Test Case 1: New User Creation
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi, I am Sarah Johnson, my email is sarah@test.com. I am looking for office space in downtown."
  }'
```

### Test Case 2: Property Search
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me properties under $5000/month",
    "user_id": "sarah@test.com"
  }'
```

### Test Case 3: Memory Recall
```bash
curl -X POST http://localhost:5000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What properties did we discuss last time?",
    "user_id": "sarah@test.com"
  }'
```

## 🔍 RAG System Features

### Automatic User Creation
- Users are automatically created when personal info is detected
- Email-based user matching prevents duplicates
- Vector database is updated in real-time

### Conversation Memory
- Chat history is stored in both MongoDB and Qdrant
- RAG context includes previous conversations
- Cross-session memory recall

### Property Search
- Fuzzy matching for property addresses
- Budget and size filtering
- Semantic search across listings

### Intent Classification
- **user_info**: Extracts and saves user contact information
- **listings_request**: Searches for commercial properties
- **general**: Casual conversation and follow-ups

## 🐛 Troubleshooting

### Qdrant Connection Issues
```bash
# Check if Qdrant is running
curl http://localhost:6333/collections

# Restart Qdrant if needed
docker stop $(docker ps -q --filter ancestor=qdrant/qdrant)
docker run -p 6333:6333 qdrant/qdrant
```

### Vector Database Sync Issues
```bash
# Reset and resync vector database
python reset_qdrant.py
python vector_db_setup.py
```

### MongoDB Connection Issues
```bash
# Check MongoDB connection
python -c "from pymongo import MongoClient; client = MongoClient('mongodb://localhost:27017'); print(client.server_info())"
```

## 📊 Data Flow

1. **User sends message** → Intent classification
2. **If user_info intent** → Extract user data → Create/match user → Update vector DB
3. **If listings_request intent** → Search properties → Return results
4. **Get RAG context** → Search vector DB for relevant data
5. **Generate response** → Aggregate all information
6. **Store conversation** → Save to MongoDB and vector DB

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