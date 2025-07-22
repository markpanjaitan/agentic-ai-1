# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file (or system environment)
load_dotenv()

# --- API Server Configuration ---
SERVER_URL = os.getenv("SERVER_URL")
GET_TOKEN_URL = os.getenv("GET_TOKEN_URL")

# --- API Authentication Credentials ---
USERNAME = os.getenv("API_USERNAME")
PASSWORD = os.getenv("API_PASSWORD")
TENANT_ID = os.getenv("X_MO_TENANT_ID")
USER_SOURCE_ID = os.getenv("X_MO_USER_SOURCE_ID")

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# --- Database Configuration ---
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', '3306')) if os.getenv('MYSQL_PORT') else 3306
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DATABASE = os.getenv('MYSQL_DATABASE')

# --- Other LLM Configurations (as seen in your .env image) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")