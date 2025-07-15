import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    DB_HOST = os.getenv('MYSQL_HOST', 'localhost')
    DB_PORT = int(os.getenv('MYSQL_PORT', 3306))
    DB_USER = os.getenv('MYSQL_USER', 'root')
    DB_PASSWORD = os.getenv('MYSQL_PASSWORD')
    DB_NAME = os.getenv('MYSQL_DATABASE', 'SchoolDb')
    
    # Google
    SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
    DRIVE_FOLDER_ID = os.getenv('DRIVE_FOLDER_ID', '1kC7xJoCO-RcJpj8R7Rc1B1FXOya_8Ayj')
    
    # Gemini
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')