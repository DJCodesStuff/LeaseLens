from flask import Flask, request, jsonify
from pymongo import MongoClient
from dotenv import load_dotenv
from models import CRERecord, UserRecord, ChatRecord
from pydantic import ValidationError
import os
import pandas as pd
from google.genai import Client
import json

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

# 👇 Predefined chatbot personality
CHATBOT_CONTEXT = (
    "You are a commercial real estate expert. "
    "Answer user queries with clarity and professionalism, focused on office leasing, investment trends, and property evaluations in major cities like New York, LA, and San Francisco."
    "Keep your responses concise and informative."
)

def clean_gemini_json(text):
    if text.startswith("```"):
        lines = text.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return text

def classify_intent(message):

    prompt = (
        "Classify the user's message into one or more of the following intents:\n\n"
        "1. \"user_info\" — message contains personal details like name, email, company, or contact info\n"
        "2. \"listings_request\" — message asks about commercial property, office spaces, location, budget, rent, etc.\n"
        "3. \"general\" — casual conversation or questions unrelated to CRM or listings\n\n"
        "Return only a **valid JSON list** of matched intents, like this:\n"
        "[\"user_info\"]\n"
        "[\"listings_request\"]\n"
        "[\"user_info\", \"listings_request\"]\n"
        "[\"general\"]\n\n"
        "**DO NOT include any explanation or text—only output the JSON list.**\n\n"
        f"User message:\n\"{message}\""
    )

    response = model.generate_content(model=modelName,contents=prompt)

    print(f"CLASSIFY AGENT: {json.loads(response.text)}")

    try:
        intents = json.loads(response.text)
        return intents
    except Exception as e:
        return ["general"]

def run_user_agent(message):
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

    response = model.generate_content(model=modelName,contents=prompt)
    raw_output = response.text.strip()
    print("RAW GEMINI OUTPUT:", raw_output)

    # ✅ Clean markdown-style code blocks (```) and "json" tag
    if raw_output.startswith("```"):
        raw_output = raw_output.replace("```json", "").replace("```", "").strip()

    try:
        extracted = json.loads(raw_output)
        print("PARSED JSON:", extracted)
        users_col.insert_one(extracted)
        return "Thanks! I've saved your info to our CRM."
    except Exception as e:
        print("❌ JSON Parsing Failed:", e)
        return f"Sorry, couldn't process your info: {str(e)}"

def run_listing_agent(message):
    prompt = (
    "Generate a MongoDB filter using the following schema for commercial listings:\n"
    "- property_address (string)\n"
    "- floor (string)\n"
    "- suite (string)\n"
    "- size_sf (number)\n"
    "- rent_per_sf_year (number)\n"
    "- broker_email (string)\n"
    "- annual_rent (number)\n"
    "- monthly_rent (number)\n"
    "- gci_on_3_years (number)\n\n"
    "Use fuzzy matching with `$regex` for addresses. Use `$lte` or `$gte` for numeric filters.\n"
    "Return only a valid JSON object. Example:\n"
    "{\n"
    "  \"property_address\": {\"$regex\": \"Broadway\", \"$options\": \"i\"},\n"
    "  \"monthly_rent\": {\"$lte\": 20000}\n"
    "}\n\n"
    f"User message:\n{message}"
)

    response = model.generate_content(model=modelName, contents=prompt)
    raw_output = clean_gemini_json(response.text.strip())

    print("LISTING AGENT RAW OUTPUT:", raw_output)

    try:
        query = json.loads(raw_output)
        print("LISTING QUERY:", query)

        # Run MongoDB fuzzy search
        listings = list(listings_col.find(query, {"_id": 0}).limit(5))

        if listings:
            return listings
        return "Sorry, no matching properties found."
    except Exception as e:
        print("❌ Listing Query Parse Error:", e)
        return f"Error while searching listings: {str(e)}"

def run_response_aggregator(model, modelName, user_info=None, listings=None, general=None):
    prompt = "Using the information below, write a friendly, cohesive response to the user:\n\n"

    if user_info:
        prompt += f"User info collected:\n{json.dumps(user_info, indent=2)}\n\n"

    if listings:
        listing_lines = [
            f"- {l.get('property_address', 'N/A')} (Suite {l.get('suite', '')}, Floor {l.get('floor', '')}) — "
            f"{l.get('size_sf', 'N/A')} sqft, ${l.get('monthly_rent', 'N/A')} /mo"
            for l in listings
        ]
        prompt += f"Matching listings:\n" + "\n".join(listing_lines) + "\n\n"

    if general:
        prompt += f"General chat reply:\n{general}\n\n"

    prompt += "Respond in a warm, conversational tone. You can address the user directly if their name is available."

    response = model.generate_content(model=modelName, contents=prompt)
    return response.text


@app.route('/chat', methods=['POST'])
def chat_with_bot():
    data = request.get_json()
    message = data.get("message")

    if not message:
        return jsonify({"error": "Message is required"}), 400

    try:
        intents = classify_intent(message)
        replies = []

        if "user_info" in intents:
            print("ENTERING USER AGENT")
            user_response = run_user_agent(message)
            print(user_response)
            replies.append(user_response)
            print("EXITING USER AGENT")

        if "listings_request" in intents:
            listing_response = run_listing_agent(message)
            if isinstance(listing_response, list):
                replies.append(f"Here are some matches:\n" + "\n\n".join([f"{l.get('property_address', 'N/A')} - ${l.get('monthly_rent', 'N/A')} /mo" for l in listing_response]))
            else:
                replies.append(listing_response)

        if "general" in intents or not replies:

            # 👇 Combine the context and user message
            prompt = f"{CHATBOT_CONTEXT}\n\nUser: {message}"
            general_reply = model.generate_content(model=modelName, contents=prompt).text
            replies.append(general_reply)

        aggregated = run_response_aggregator(
            model, modelName,
            user_info = user_response,
            listings = listing_response,
            general = general_reply
        )
        return jsonify({
            "response": aggregated
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
        user = UserRecord(**data)
        users_col.insert_one(user.dict())
        return jsonify({'message': 'User inserted'}), 201
    except ValidationError as e:
        return jsonify({'error': e.errors()}), 400
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

# === CHAT_HISTORY route (JSON input) ===
@app.route('/chat_history', methods=['POST'])
def add_chat():
    try:
        data = request.get_json()
        chat = ChatRecord(**data)
        chat_col.insert_one(chat.dict())
        return jsonify({'message': 'Chat inserted'}), 201
    except ValidationError as e:
        return jsonify({'error': e.errors()}), 400
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500

if __name__ == '__main__':
    app.run(debug=True)
