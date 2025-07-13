#!/usr/bin/env python3
"""
Quick Setup Script for CRM Chatbot with RAG
This script helps you set up the environment and dependencies
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def check_docker():
    """Check if Docker is running"""
    try:
        result = subprocess.run("docker ps", shell=True, capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False

def main():
    print("🚀 CRM Chatbot with RAG - Quick Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env file from template...")
        env_content = """# MongoDB Configuration
MONGO_URI=mongodb://localhost:27017/CRM

# Google Gemini API
GEMINI_API_KEY=your_gemini_api_key_here

# Qdrant Configuration (optional, defaults to localhost:6333)
QDRANT_URL=http://localhost:6333
"""
        with open(".env", "w") as f:
            f.write(env_content)
        print("✅ .env file created")
        print("⚠️  Please update the .env file with your actual API keys")
    else:
        print("✅ .env file already exists")
    
    # Install dependencies
    if not run_command("pip install -r requirements.txt", "Installing Python dependencies"):
        print("❌ Failed to install dependencies")
        sys.exit(1)
    
    # Check Docker
    if check_docker():
        print("✅ Docker is running")
        
        # Start Qdrant
        print("🔄 Starting Qdrant vector database...")
        qdrant_command = "docker run -d --name qdrant -p 6333:6333 qdrant/qdrant"
        if run_command(qdrant_command, "Starting Qdrant"):
            print("✅ Qdrant started successfully")
        else:
            print("⚠️  Qdrant might already be running or failed to start")
    else:
        print("⚠️  Docker is not running. Please start Docker Desktop and run:")
        print("   docker run -d --name qdrant -p 6333:6333 qdrant/qdrant")
    
    print("\n🎉 Setup completed!")
    print("\n📋 Next steps:")
    print("1. Update .env file with your Google Gemini API key")
    print("2. Make sure MongoDB is running")
    print("3. Make sure Qdrant is running (docker ps)")
    print("4. Run: python vector_db_setup.py")
    print("5. Run: python app.py")
    print("\n🧪 Test the application:")
    print("curl -X POST http://localhost:5000/chat \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"message\": \"Hi, I am John Doe, john@example.com. I am looking for office space.\"}'")

if __name__ == "__main__":
    main() 