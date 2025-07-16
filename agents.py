"""
Agent functions for the CRM Chatbot
Contains all the AI agents for intent classification, user info extraction, 
listing search, and response aggregation.
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from user_data import UserDataManager
from Agents.genai_wrapper import GenAIWrapper

wrapper = GenAIWrapper()
wrapper.load_graph()

# Enhanced chatbot personality with RAG context
CHATBOT_CONTEXT = (
    "You are a commercial real estate expert with access to a comprehensive database of properties, "
    "user information, and conversation history. Use the provided context to give personalized, "
    "informed responses. Focus on office leasing, investment trends, and property evaluations in "
    "major cities like New York, LA, and San Francisco. Keep responses concise and informative."
)

def clean_gemini_json(text):
    """Clean Gemini JSON output by removing markdown formatting"""
    if text.startswith("```"):
        lines = text.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return text

def classify_intent(message: str, model, modelName: str) -> List[str]:
    """Classify user message into intents"""
    prompt = (
        "Classify the user's message into one or more of the following intents:\n\n"
        "1. \"user_info\" — message contains NEW personal details like name, email, company, or contact info that needs to be saved\n"
        "2. \"listings_request\" — message asks about commercial property, office spaces, location, budget, rent, etc.\n"
        "3. \"general\" — casual conversation, questions about previous conversations, general inquiries, or anything not requiring new user info\n\n"
        "Return only a **valid JSON list** of matched intents, like this:\n"
        "[\"user_info\"]\n"
        "[\"listings_request\"]\n"
        "[\"user_info\", \"listings_request\"]\n"
        "[\"general\"]\n\n"
        "**DO NOT include any explanation or text—only output the JSON list.**\n\n"
        f"User message:\n\"{message}\""
    )

    response = model.generate_content(model=modelName, contents=prompt)
    print(f"CLASSIFY AGENT: {json.loads(response.text)}")

    try:
        intents = json.loads(response.text)
        return intents
    except Exception as e:
        return ["general"]

def run_user_agent(message: str, model, modelName: str, data_manager: UserDataManager) -> str:
    """Extract and save user information from message"""
    print(message)

    prompt = (
        "Extract the user's contact and intent information from the message below. "
        "Return the result as a JSON object with the following fields:\n\n"
        "- name (string)\n"
        "- email (string)\n"
        "- company (string, optional)\n"
        "- requirement (string, a short summary of what they're looking for)\n\n"
        "Only return the JSON object. Do not include any explanation or commentary.\n\n"
        "Example:\n"
        "{\n"
        '  "name": "Arya Stark",\n'
        '  "email": "arya@winterfell.com",\n'
        '  "company": "Stark Industries",\n'
        '  "requirement": "Looking for an office in SoHo under $8000"\n'
        "}\n\n"
        f"User Message:\n{message}"
    )

    response = model.generate_content(model=modelName, contents=prompt)
    raw_output = response.text.strip()
    print("RAW GEMINI OUTPUT:", raw_output)

    if raw_output.startswith("```"):
        raw_output = raw_output.replace("```json", "").replace("```", "").strip()

    try:
        extracted = json.loads(raw_output)
        print("PARSED JSON:", extracted)
        data_manager.create_user(extracted)
        return "Thanks! I've saved your info to our CRM."
    except Exception as e:
        print("❌ JSON Parsing Failed:", e)
        return f"Sorry, couldn't process your info: {str(e)}"

def run_listing_agent(message: str, model, modelName: str, listings_col, rag_context: Optional[Dict] = None) -> Any:
    """Search for commercial property listings"""
    # # Enhanced prompt with RAG context
    # context_info = ""
    # if rag_context and rag_context.get("listings"):
    #     context_info = f"\n\nRelevant property context:\n"
    #     for listing in rag_context["listings"][:2]:  # Use top 2 relevant listings
    #         context_info += f"- {listing.get('property_address', 'N/A')}: ${listing.get('monthly_rent', 'N/A')}/mo, {listing.get('size_sf', 'N/A')} sqft\n"
    
    # prompt = (
    #     f"Generate a MongoDB filter using the following schema for commercial listings:\n"
    #     f"- property_address (string)\n"
    #     f"- floor (string)\n"
    #     f"- suite (string)\n"
    #     f"- size_sf (number)\n"
    #     f"- rent_per_sf_year (number)\n"
    #     f"- broker_email (string)\n"
    #     f"- annual_rent (number)\n"
    #     f"- monthly_rent (number)\n"
    #     f"- gci_on_3_years (number)\n\n"
    #     f"Use fuzzy matching with `$regex` for addresses. Use `$lte` or `$gte` for numeric filters.\n"
    #     f"Return only a valid JSON object. Example:\n"
    #     f"{{\n"
    #     f"  \"property_address\": {{\"$regex\": \"Broadway\", \"$options\": \"i\"}},\n"
    #     f"  \"monthly_rent\": {{\"$lte\": 20000}}\n"
    #     f"}}\n\n"
    #     f"{context_info}\n"
    #     f"User message:\n{message}"
    # )

    # response = model.generate_content(model=modelName, contents=prompt)
    # raw_output = clean_gemini_json(response.text.strip())

    # print("LISTING AGENT RAW OUTPUT:", raw_output)

    # try:
    #     query = json.loads(raw_output)
    #     print("LISTING QUERY:", query)

    #     # Run MongoDB fuzzy search
    #     listings = list(listings_col.find(query, {"_id": 0}).limit(5))

    #     if listings:
    #         return listings
    #     return "Sorry, no matching properties found."
    # except Exception as e:
    #     print("❌ Listing Query Parse Error:", e)
    #     return f"Error while searching listings: {str(e)}"

    response = wrapper.generate(message)
    return response
    

def run_response_aggregator(model, modelName: str, user_info=None, listings=None, general=None, rag_context=None) -> str:
    """Aggregate all agent responses into a cohesive reply"""
    # Enhanced prompt with RAG context (but don't show chat history to user)
    context_section = ""
    if rag_context:
        context_section = "\n\n=== RELEVANT CONTEXT ===\n"
        
        if rag_context.get("user_info"):
            context_section += "User Information:\n"
            for user in rag_context["user_info"]:
                context_section += f"- {user.get('name', 'N/A')} ({user.get('email', 'N/A')})\n"
        
        # Remove chat history from visible context - let RAG handle it invisibly
        # if rag_context.get("chat_history"):
        #     context_section += "\nRecent Conversation History:\n"
        #     for chat in rag_context["chat_history"][:3]:  # Last 3 conversations
        #         context_section += f"- User: {chat.get('message', 'N/A')[:100]}...\n"
        #         context_section += f"  Bot: {chat.get('response', 'N/A')[:100]}...\n"
        
        if rag_context.get("listings"):
            context_section += "\nRelevant Properties:\n"
            for listing in rag_context["listings"][:2]:
                context_section += f"- {listing.get('property_address', 'N/A')}: ${listing.get('monthly_rent', 'N/A')}/mo\n"
    
    prompt = f"Using the information below, write a friendly, cohesive response to the user:{context_section}\n\n"

    if user_info:
        prompt += f"User info collected:\n{json.dumps(user_info, indent=2)}\n\n"

    if listings:
        if isinstance(listings, list):
            listing_lines = [
                f"- {l.get('property_address', 'N/A')} (Suite {l.get('suite', '')}, Floor {l.get('floor', '')}) — "
                f"{l.get('size_sf', 'N/A')} sqft, ${l.get('monthly_rent', 'N/A')} /mo"
                for l in listings
            ]
            prompt += f"Matching listings:\n" + "\n".join(listing_lines) + "\n\n"
        else:
            prompt += f"Listing search result:\n{listings}\n\n"

    if general:
        prompt += f"General chat reply:\n{general}\n\n"

    prompt += "Respond in a warm, conversational tone. You can address the user directly if their name is available. Use the context to provide personalized responses. Do NOT mention previous conversations or chat history in your response - just respond naturally to the current message."

    response = model.generate_content(model=modelName, contents=prompt)
    return response.text

def process_chat_message(message: str, user_id: str, session_id: str, model, modelName: str, 
                        data_manager: UserDataManager, listings_col, vdb_manager=None) -> Dict[str, Any]:
    """
    Main function to process a chat message through all agents
    Returns a dictionary with response, session_id, and user_id
    """
    try:
        # Get RAG context if vector database is available
        rag_context = None
        if vdb_manager:
            try:
                rag_context = vdb_manager.get_rag_context(message, user_id, session_id)
                print("🔍 RAG Context retrieved:", {k: len(v) for k, v in rag_context.items()})
            except Exception as e:
                print(f"❌ Error getting RAG context: {e}")

        intents = classify_intent(message, model, modelName)
        replies = []
        user_response, listing_response, general_reply = None, None, None
        user_result = None
        show_welcome_message = False

        if "user_info" in intents:
            print("🔍 Detected user_info intent, extracting user data...")
            
            # Extract user info from message
            user_result = data_manager.extract_user_info(message)
            print("📋 Extracted user result:", user_result)
            
            if user_result:
                extracted_email = user_result.get("email", "")
                
                # Check if user already exists by email
                existing_user = data_manager.users_col.find_one({"email": extracted_email})
                
                if existing_user:
                    print(f"✅ Found existing user with email {extracted_email}")
                    user_id = existing_user.get("user_id", extracted_email)
                    user_result = None  # Don't create duplicate
                    
                    # Only show welcome message if this is a new session or if user_id was "anonymous"
                    if user_id == "anonymous" or not data_manager.chat_col.find_one({"user_id": user_id, "session_id": session_id}):
                        show_welcome_message = True
                        replies.append(f"Welcome back! I found your existing profile.")
                else:
                    # Create new user
                    user_id = extracted_email
                    print("👤 Creating new user with data:", user_result)
                    create_result = data_manager.create_user(user_result)
                    print("✅ User creation result:", create_result)
                    
                    # Add to vector database if available
                    if vdb_manager:
                        vdb_manager.add_document('Users', user_result, vdb_manager.create_user_document)
                    
                    replies.append("Thanks! I've saved your info to our CRM.")
            else:
                print("❌ Failed to extract user info")
                replies.append("Sorry, I couldn't process your contact info.")

        if "listings_request" in intents:
            listing_response = run_listing_agent(message, model, modelName, listings_col, rag_context)
            if isinstance(listing_response, list):
                replies.append(f"Here are some matches:\n" + "\n\n".join([f"{l.get('property_address', 'N/A')} - ${l.get('monthly_rent', 'N/A')} /mo" for l in listing_response]))
            else:
                replies.append(listing_response)

        if "general" in intents or not replies:
            prompt = f"{CHATBOT_CONTEXT}\n\nUser: {message}"
            general_reply = model.generate_content(model=modelName, contents=prompt).text
            replies.append(general_reply)

        aggregated = run_response_aggregator(
            model, modelName,
            user_info=user_result if user_result else None,
            listings=listing_response if listing_response else None,
            general=general_reply if general_reply else None,
            rag_context=rag_context
        )

        return {
            "response": aggregated,
            "session_id": session_id,
            "user_id": user_id,
            "user_result": user_result
        }

    except Exception as e:
        print(f"❌ Error in process_chat_message: {e}")
        return {
            "response": f"Sorry, I encountered an error: {str(e)}",
            "session_id": session_id,
            "user_id": user_id,
            "user_result": None
        } 