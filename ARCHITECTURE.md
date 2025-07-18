# CRM Chatbot Architecture

## System Overview

The CRM Chatbot is a sophisticated commercial real estate assistant that combines AI-powered conversation with RAG (Retrieval-Augmented Generation) capabilities. The system provides intelligent property search, user management, and contextual conversations using multiple AI agents.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Web Client / Postman / API Client                                             │
│  • POST /chat                                                                   │
│  • POST /upload_listings                                                        │
│  • POST /users                                                                  │
│  • GET /crm/conversations/{user_id}                                            │
│  • POST /admin/sync-vector-db                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER (Flask)                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  app.py                                                                         │
│  ├── /chat (POST) - Main chat endpoint                                         │
│  ├── /upload_listings (POST) - CSV property upload                            │
│  ├── /users (POST) - User creation                                             │
│  ├── /crm/conversations/{user_id} (GET) - Chat history                         │
│  └── /admin/sync-vector-db (POST) - Vector DB sync                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              AGENT LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│  agents.py                                                                      │
│  ├── process_chat_message() - Main orchestrator                               │
│  ├── classify_intent() - Intent classification                                │
│  ├── run_user_agent() - User info extraction                                  │
│  ├── run_listing_agent() - Property search                                    │
│  └── run_response_aggregator() - Response synthesis                           │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│  user_data.py                                                                   │
│  └── UserDataManager - User & chat operations                                  │
│                                                                                 │
│  models.py                                                                      │
│  ├── CRERecord - Property data model                                           │
│  ├── UserRecord - User data model                                              │
│  └── ChatRecord - Chat data model                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STORAGE LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│  MongoDB (Primary Database)                                                    │
│  ├── Users Collection                                                          │
│  ├── Listings Collection                                                       │
│  ├── chat_history Collection                                                   │
│  └── sessions Collection                                                       │
│                                                                                 │
│  Qdrant (Vector Database)                                                      │
│  ├── Users Collection (embeddings)                                             │
│  ├── chat_history Collection (embeddings)                                      │
│  ├── Listings Collection (embeddings)                                          │
│  └── sessions Collection (embeddings)                                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SERVICES                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Google Gemini AI                                                              │
│  └── gemini-2.5-flash model                                                    │
│                                                                                 │
│  Sentence Transformers                                                         │
│  └── all-MiniLM-L6-v2 (384-dim embeddings)                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

<img width="971" height="971" alt="Untitled Diagram drawio (2)" src="https://github.com/user-attachments/assets/e27f9ef8-a4be-469b-9143-cbeec0f02893" />


## Component Details

### 1. API Layer (`app.py`)
**Purpose**: HTTP request handling and routing
- **Flask Application**: Main web framework
- **Route Handlers**: 5 main endpoints for different functionalities
- **Session Management**: Automatic session creation and user tracking
- **Error Handling**: Comprehensive error responses

**Key Endpoints**:
- `POST /chat` - Main conversational interface
- `POST /upload_listings` - Bulk property data import
- `POST /users` - User management
- `GET /crm/conversations/{user_id}` - Conversation history
- `POST /admin/sync-vector-db` - Vector database synchronization

### 2. Agent Layer (`agents.py`)
**Purpose**: AI-powered business logic and conversation management

**Core Functions**:
- **`process_chat_message()`**: Main orchestrator that coordinates all agents
- **`classify_intent()`**: Determines user intent (user_info, listings_request, general)
- **`run_user_agent()`**: Extracts and processes user contact information
- **`run_listing_agent()`**: Searches commercial properties using MongoDB queries
- **`run_response_aggregator()`**: Synthesizes final response using RAG context

**Intent Classification**:
- `user_info`: New personal details extraction
- `listings_request`: Property search queries
- `general`: Casual conversation and follow-ups

### 3. Data Management Layer (`user_data.py`)
**Purpose**: User and chat data operations
- **UserDataManager**: Centralized user and chat operations
- **Data Validation**: Pydantic model integration
- **AI Integration**: User info extraction using Gemini

**Key Methods**:
- `create_user()`: User creation with validation
- `extract_user_info()`: AI-powered contact extraction
- `add_chat_entry()`: Chat history storage
- `get_chat_history()`: Conversation retrieval

### 4. Data Models (`models.py`)
**Purpose**: Data validation and structure definition
- **CRERecord**: Commercial real estate property schema
- **UserRecord**: User profile schema
- **ChatRecord**: Conversation entry schema

### 5. Vector Database Layer (`vector_db_setup.py`)
**Purpose**: RAG system implementation using Qdrant

**VectorDatabaseManager**:
- **Embedding Generation**: Sentence transformers for text vectorization
- **Collection Management**: 4 collections (Users, chat_history, Listings, sessions)
- **RAG Context**: Semantic search across all data types
- **Sync Operations**: MongoDB to Qdrant data synchronization

**RAG Features**:
- Semantic search across user profiles, chat history, and properties
- Context-aware responses using previous conversations
- Automatic embedding generation and storage

## Data Flow

### 1. Chat Message Processing
```
User Message → Flask Route → Intent Classification → Agent Selection → RAG Context → Response Generation → Storage
```

### 2. RAG Context Retrieval
```
Query → Vector Search → User Info + Chat History + Listings → Context Assembly → LLM Response
```

### 3. Data Synchronization
```
MongoDB Collections → Embedding Generation → Qdrant Storage → Vector Search Ready
```

## Key Features

### 1. Multi-Agent Architecture
- **Intent Classification**: Smart message categorization
- **User Management**: Automatic user creation and profile matching
- **Property Search**: Fuzzy matching with MongoDB queries
- **Response Synthesis**: Context-aware response generation

### 2. RAG System
- **Semantic Search**: 384-dimensional embeddings using all-MiniLM-L6-v2
- **Multi-Collection Search**: Users, chat history, listings, and sessions
- **Context Assembly**: Intelligent context selection for responses
- **Real-time Updates**: Automatic vector database updates

### 3. Session Management
- **Multi-Session Support**: Users can have multiple conversation sessions
- **Session Persistence**: Automatic session creation and tracking
- **Cross-Session Memory**: RAG context spans all user sessions

### 4. Data Validation
- **Pydantic Models**: Type-safe data validation
- **CSV Import**: Bulk property data with validation
- **Error Handling**: Comprehensive error responses

## Technology Stack

### Backend
- **Flask**: Web framework
- **MongoDB**: Primary database
- **Qdrant**: Vector database
- **Google Gemini**: AI model (gemini-2.5-flash)

### AI/ML
- **Sentence Transformers**: Text embeddings (all-MiniLM-L6-v2)
- **RAG**: Retrieval-Augmented Generation
- **Intent Classification**: Multi-intent detection

### Data Processing
- **Pandas**: CSV processing
- **Pydantic**: Data validation
- **PyMongo**: MongoDB operations

## Security & Performance

### Security
- Environment variable configuration
- Input validation with Pydantic
- Error handling without data exposure

### Performance
- Vector database for fast semantic search
- MongoDB indexing for efficient queries
- Asynchronous embedding generation
- Connection pooling for database operations

## Scalability Considerations

### Horizontal Scaling
- Stateless Flask application
- External database dependencies
- Docker containerization ready

### Performance Optimization
- Vector database for semantic search
- MongoDB aggregation pipelines
- Efficient embedding generation
- Connection pooling

## Deployment Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │    │   Flask App 1   │    │   Flask App 2   │
│   (Nginx/ALB)   │◄──►│   (Container)   │    │   (Container)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────────────────────────┐
                       │           MongoDB Cluster           │
                       │  (Primary + Replica Set)            │
                       └─────────────────────────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Qdrant        │
                       │   (Vector DB)   │
                       └─────────────────┘
```

This architecture provides a robust, scalable, and intelligent CRM chatbot system with advanced RAG capabilities for commercial real estate applications. 
