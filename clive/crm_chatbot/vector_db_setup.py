"""
Vector Database Setup for CRM RAG System
This script sets up Qdrant vector database with collections for:
- Users
- Chat History  
- Listings
- Sessions
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    Filter, FieldCondition, MatchValue, Range
)
from sentence_transformers import SentenceTransformer
import numpy as np
import uuid

load_dotenv()

class VectorDatabaseManager:
    def __init__(self):
        # Initialize MongoDB connection
        self.mongo_client = MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client['CRM']
        
        # Initialize Qdrant client (local)
        self.qdrant_client = QdrantClient("localhost", port=6333)
        
        # Initialize sentence transformer for embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Collection names
        self.collections = {
            'Users': 'Users',
            'chat_history': 'chat_history', 
            'Listings': 'Listings',
            'sessions': 'sessions'
        }
        
        # Vector dimensions (all-MiniLM-L6-v2 produces 384-dimensional vectors)
        self.vector_size = 384
        
    def create_collections(self):
        """Create Qdrant collections for all CRM data types"""
        print("🔄 Creating Qdrant collections...")
        
        for collection_name in self.collections.values():
            try:
                # Check if collection exists
                collections = self.qdrant_client.get_collections()
                collection_names = [c.name for c in collections.collections]
                
                if collection_name not in collection_names:
                    self.qdrant_client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.vector_size,
                            distance=Distance.COSINE
                        )
                    )
                    print(f"✅ Created collection: {collection_name}")
                else:
                    print(f"ℹ️  Collection already exists: {collection_name}")
                    
            except Exception as e:
                print(f"❌ Error creating collection {collection_name}: {e}")
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        if not text:
            return [0.0] * self.vector_size
        return self.embedding_model.encode(text).tolist()
    
    def create_user_document(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Create a document for user embedding"""
        return {
            "id": str(uuid.uuid4()),
            "type": "user",
            "user_id": user.get("user_id", ""),
            "name": user.get("name", ""),
            "email": user.get("email", ""),
            "role": user.get("role", "user"),
            "text_for_embedding": f"User: {user.get('name', '')} with email {user.get('email', '')} has role {user.get('role', 'user')}",
            "metadata": {
                "created_at": datetime.utcnow().isoformat(),
                "source": "mongodb_users"
            }
        }
    
    def create_chat_document(self, chat: Dict[str, Any]) -> Dict[str, Any]:
        """Create a document for chat history embedding"""
        return {
            "id": str(uuid.uuid4()),
            "type": "chat",
            "chat_id": chat.get("chat_id", ""),
            "user_id": chat.get("user_id", ""),
            "session_id": chat.get("session_id", ""),
            "message": chat.get("message", ""),
            "response": chat.get("response", ""),
            "timestamp": chat.get("timestamp", ""),
            "text_for_embedding": f"User message: {chat.get('message', '')} | Bot response: {chat.get('response', '')}",
            "metadata": {
                "timestamp": chat.get("timestamp", ""),
                "session_id": chat.get("session_id", ""),
                "source": "mongodb_chat_history"
            }
        }
    
    def create_listing_document(self, listing: Dict[str, Any]) -> Dict[str, Any]:
        """Create a document for listing embedding"""
        return {
            "id": str(uuid.uuid4()),
            "type": "listing",
            "unique_id": listing.get("unique_id", ""),
            "property_address": listing.get("property_address", ""),
            "floor": listing.get("floor", ""),
            "suite": listing.get("suite", ""),
            "size_sf": listing.get("size_sf", 0),
            "rent_per_sf_year": listing.get("rent_per_sf_year", 0),
            "annual_rent": listing.get("annual_rent", 0),
            "monthly_rent": listing.get("monthly_rent", 0),
            "text_for_embedding": f"Property at {listing.get('property_address', '')} on floor {listing.get('floor', '')} suite {listing.get('suite', '')} with {listing.get('size_sf', 0)} sqft, monthly rent ${listing.get('monthly_rent', 0)}",
            "metadata": {
                "size_sf": listing.get("size_sf", 0),
                "monthly_rent": listing.get("monthly_rent", 0),
                "annual_rent": listing.get("annual_rent", 0),
                "source": "mongodb_listings"
            }
        }
    
    def create_session_document(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Create a document for session embedding"""
        return {
            "id": str(uuid.uuid4()),
            "type": "session",
            "session_id": session.get("session_id", ""),
            "user_id": session.get("user_id", ""),
            "created_at": session.get("created_at", ""),
            "status": session.get("status", "active"),
            "text_for_embedding": f"Session {session.get('session_id', '')} for user {session.get('user_id', '')} created at {session.get('created_at', '')}",
            "metadata": {
                "created_at": session.get("created_at", ""),
                "status": session.get("status", "active"),
                "source": "mongodb_sessions"
            }
        }
    
    def sync_mongodb_to_qdrant(self):
        """Sync all MongoDB collections to Qdrant"""
        print("🔄 Syncing MongoDB data to Qdrant...")
        
        # Sync Users
        print("📊 Syncing users...")
        users = list(self.db.Users.find({}))
        self._sync_collection(users, 'Users', self.create_user_document)
        
        # Sync Chat History
        print("💬 Syncing chat history...")
        chats = list(self.db.chat_history.find({}))
        self._sync_collection(chats, 'chat_history', self.create_chat_document)
        
        # Sync Listings
        print("🏢 Syncing listings...")
        listings = list(self.db.Listings.find({}))
        self._sync_collection(listings, 'Listings', self.create_listing_document)
        
        # Sync Sessions
        print("🔄 Syncing sessions...")
        sessions = list(self.db.sessions.find({}))
        self._sync_collection(sessions, 'sessions', self.create_session_document)
        
        print("✅ MongoDB to Qdrant sync completed!")
    
    def _sync_collection(self, documents: List[Dict], collection_name: str, document_creator):
        """Helper method to sync a collection"""
        if not documents:
            print(f"ℹ️  No documents found in {collection_name}")
            return
            
        points = []
        for doc in documents:
            try:
                qdrant_doc = document_creator(doc)
                embedding = self.get_embedding(qdrant_doc["text_for_embedding"])
                
                point = PointStruct(
                    id=qdrant_doc["id"],
                    vector=embedding,
                    payload=qdrant_doc
                )
                points.append(point)
            except Exception as e:
                print(f"❌ Error processing document in {collection_name}: {e}")
        
        if points:
            try:
                # Clear existing data and insert new
                self.qdrant_client.delete(collection_name=collection_name, points_selector=Filter(must=[]))
                self.qdrant_client.upsert(collection_name=collection_name, points=points)
                print(f"✅ Synced {len(points)} documents to {collection_name}")
            except Exception as e:
                print(f"❌ Error syncing {collection_name}: {e}")
    
    def search_similar(self, query: str, collection_name: str, limit: int = 5, filters: Optional[Dict] = None) -> List[Dict]:
        """Search for similar documents in a collection"""
        try:
            query_embedding = self.get_embedding(query)
            
            # Build filter if provided
            qdrant_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
                qdrant_filter = Filter(must=conditions)
            
            search_result = self.qdrant_client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                query_filter=qdrant_filter
            )
            
            return [hit.payload for hit in search_result]
            
        except Exception as e:
            print(f"❌ Error searching {collection_name}: {e}")
            return []
    
    def get_rag_context(self, query: str, user_id: str = None, session_id: str = None) -> Dict[str, Any]:
        """Get RAG context for a query based on relevant data"""
        context = {
            "user_info": [],
            "chat_history": [],
            "listings": [],
            "sessions": []
        }
        
        print(f"🔍 RAG Debug - Query: '{query}', User: '{user_id}', Session: '{session_id}'")
        
        # Get user context if user_id provided
        if user_id:
            user_results = self.search_similar(
                f"user {user_id}", 
                'Users', 
                limit=3,
                filters={"user_id": user_id}
            )
            context["user_info"] = user_results
            print(f"👤 User search results: {len(user_results)}")
        
        # Get chat history context - only filter by user_id to find all previous conversations
        chat_filters = {}
        if user_id:
            chat_filters["user_id"] = user_id
        # Remove session_id filter to find all previous conversations for the user
            
        # Search for user's chat history using a general query about previous conversations
        chat_search_query = f"previous conversation history for user {user_id}" if user_id else "chat history"
        print(f"💬 Chat search query: '{chat_search_query}'")
        print(f"🔍 Chat filters: {chat_filters}")
        
        chat_results = self.search_similar(
            chat_search_query, 
            'chat_history', 
            limit=5,
            filters=chat_filters if chat_filters else None
        )
        context["chat_history"] = chat_results
        print(f"💬 Chat search results: {len(chat_results)}")
        
        # Get relevant listings
        listing_results = self.search_similar(query, 'Listings', limit=3)
        context["listings"] = listing_results
        print(f"🏢 Listing search results: {len(listing_results)}")
        
        # Get session context if session_id provided
        if session_id:
            session_results = self.search_similar(
                f"session {session_id}", 
                'sessions', 
                limit=1,
                filters={"session_id": session_id}
            )
            context["sessions"] = session_results
            print(f"🔄 Session search results: {len(session_results)}")
        
        return context
    
    def add_document(self, collection_name: str, document: Dict[str, Any], document_creator):
        """Add a single document to Qdrant"""
        try:
            qdrant_doc = document_creator(document)
            embedding = self.get_embedding(qdrant_doc["text_for_embedding"])
            
            point = PointStruct(
                id=qdrant_doc["id"],
                vector=embedding,
                payload=qdrant_doc
            )
            
            self.qdrant_client.upsert(collection_name=collection_name, points=[point])
            print(f"✅ Added document to {collection_name}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding document to {collection_name}: {e}")
            return False

def main():
    """Main function to set up the vector database"""
    print("🚀 Setting up Vector Database for CRM RAG System...")
    
    # Initialize vector database manager
    vdb_manager = VectorDatabaseManager()
    
    # Create collections
    vdb_manager.create_collections()
    
    # Sync data from MongoDB
    vdb_manager.sync_mongodb_to_qdrant()
    
    print("🎉 Vector Database setup completed!")
    print("\n📋 Next steps:")
    print("1. Install Qdrant server: docker run -p 6333:6333 qdrant/qdrant")
    print("2. Update your .env file with QDRANT_URL=http://localhost:6333")
    print("3. Import VectorDatabaseManager in your app.py")
    print("4. Use get_rag_context() in your agents for enhanced responses")

if __name__ == "__main__":
    main() 