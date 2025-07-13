# CRM Chatbot API Contract

## Base URL
```
http://localhost:5000/
```

---

## Endpoints

### 1. **POST `/chat`**
**Description:** Send a message to the chatbot and receive a response (RAG-enabled).

#### Request Body
```json
{
  "message": "Show me offices in downtown.",
  "user_id": "user1@example.com",      // optional
  "session_id": "session_2024-07-13T12:00:00Z" // optional
}
```

#### Response
```json
{
  "status": "success",
  "response": "Here are some office listings in downtown...",
  "session_id": "session_2024-07-13T12:00:00Z",
  "user_id": "user1@example.com",
  "processing_time": 0.123
}
```

---

### 2. **POST `/upload_docs`**
**Description:** Upload property listings in CSV, JSON, TXT, or PDF format.

#### Form Data
- `file`: (file) One or more files containing listings.

#### Response
```json
{
  "status": "success",
  "message": "Documents processed successfully",
  "processed_files": [
    {
      "filename": "test_listings.json",
      "type": "json",
      "records_inserted": 5,
      "rejected_records": 0,
      "errors": [],
      "processing_time": 0.02
    }
  ],
  "total_processing_time": 0.02,
  "vector_db_updated": true,
  "processing_time": 0.02
}
```

---

### 3. **POST `/users`**  
**Description:** Create a new user.

#### Request Body
```json
{
  "user_id": "user1@example.com",
  "name": "User One",
  "email": "user1@example.com",
  "role": "user"
}
```

#### Response
```json
{
  "status": "success",
  "message": "User inserted",
  "processing_time": 0.01
}
```

---

### 4. **GET `/crm/get_user/<user_id>`**
**Description:** Get user info by user_id.

#### Response
```json
{
  "status": "success",
  "user": {
    "user_id": "user1@example.com",
    "name": "User One",
    "email": "user1@example.com",
    "role": "user"
  },
  "processing_time": 0.01
}
```

---

### 5. **PUT `/crm/update_user/<user_id>`**
**Description:** Update user info.

#### Request Body
```json
{
  "name": "User One Updated"
}
```

#### Response
```json
{
  "status": "success",
  "message": "User updated",
  "processing_time": 0.01
}
```

---

### 6. **DELETE `/crm/delete_user/<user_id>`**
**Description:** Delete a user.

#### Response
```json
{
  "status": "success",
  "message": "User deleted",
  "processing_time": 0.01
}
```

---

### 7. **GET `/crm/conversations/<user_id>`**
**Description:** Get all conversation sessions for a user, grouped by session.

#### Response
```json
{
  "status": "success",
  "user_id": "user1@example.com",
  "total_sessions": 2,
  "sessions": [
    {
      "session_id": "session_2024-07-13T12:00:00Z",
      "user_id": "user1@example.com",
      "status": "Inquiring",
      "conversations": [
        {
          "chat_id": "...",
          "timestamp": "...",
          "message": "...",
          "response": "..."
        }
      ]
    }
  ],
  "processing_time": 0.02
}
```

---

### 8. **POST `/reset`**
**Description:** Delete all chat history (global or for a specific user).

#### Request Body (optional)
```json
{
  "user_id": "user1@example.com"
}
```

#### Response
```json
{
  "status": "success",
  "message": "All chat history for user user1@example.com deleted.",
  "deleted_count": 12,
  "processing_time": 0.01
}
```

---

### 9. **POST `/crm/resolve_session/<session_id>`**
**Description:** Mark a session as resolved.

#### Response
```json
{
  "status": "success",
  "message": "Session session_2024-07-13T12:00:00Z marked as Resolved.",
  "processing_time": 0.01
}
```

---

### 10. **POST `/admin/sync-vector-db`**
**Description:** Manually sync MongoDB data to Qdrant (vector DB).

#### Response
```json
{
  "status": "success",
  "message": "Vector database sync completed successfully",
  "processing_time": 0.05
}
```

---

## **General Notes**
- All responses include `status` and `processing_time`.
- All endpoints return JSON.
- Error responses include `status: "error"` and an `error` message.

---

## **Sample Listing Record Schema**
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