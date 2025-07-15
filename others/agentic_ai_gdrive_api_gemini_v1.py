import pymysql
import re
import os
import io
import json
from dotenv import load_dotenv
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import PyPDF2
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# ------------------------
# 🏥 Medical History Processing
# ------------------------
def extract_medical_history(pdf_text):
    """Extract structured medical history from PDF text using LLM."""
    medical_prompt = f"""
Extract medical history information from this document and format as JSON:
{pdf_text[:10000]}  # Limiting to first 10k chars

The PDF contains student medical records. Extract:
1. Each student's full name and email
2. All medical conditions with dates
3. Allergies and current medications

Output format:
{{
    "students": [
        {{
            "name": "Full Name",
            "email": "email@domain.com",
            "conditions": [
                {{
                    "condition": "Condition Name",
                    "date": "YYYY-MM-DD",
                    "severity": "mild/moderate/severe",
                    "chronic": true/false
                }}
            ],
            "allergies": ["Allergen1", "Allergen2"],
            "current_medications": ["Med1", "Med2"]
        }}
    ]
}}
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        response = model.generate_content(medical_prompt)
        return response.text
    except Exception as e:
        print(f"❌ Error extracting medical history: {e}")
        return None

def calculate_health_score(medical_data):
    """Calculate a health score (0-100, higher is better)."""
    if not medical_data or 'students' not in medical_data:
        return None
    
    health_scores = {}
    
    for student in medical_data['students']:
        score = 100  # Starting score (perfect health)
        
        # Deduct points for conditions
        for condition in student.get('conditions', []):
            severity_map = {'mild': 5, 'moderate': 15, 'severe': 30}
            score -= severity_map.get(condition.get('severity', 'mild'), 5)
            if condition.get('chronic', False):
                score -= 10
                
        # Deduct points for allergies
        score -= len(student.get('allergies', [])) * 3
        
        # Deduct points for medications
        score -= len(student.get('current_medications', [])) * 2
        
        health_scores[student['email'].lower()] = max(0, score)  # Normalize email case
    
    return health_scores

# ------------------------
# 📁 Enhanced Google Drive Functions
# ------------------------
def initialize_drive_service():
    """Initialize the Google Drive API service with detailed debugging."""
    try:
        print("\n🔧 Initializing Google Drive service...")
        service_account_file = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
        
        if not service_account_file:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE not found in .env")
        
        print(f"✅ Using service account file: {service_account_file}")
        
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        drive_service = build('drive', 'v3', credentials=credentials)
        print("🚀 Google Drive service initialized successfully")
        return drive_service
    except Exception as e:
        print(f"❌ Failed to initialize Google Drive service: {e}")
        return None

def search_files(drive_service, query, mime_type=None):
    """Search for files in Google Drive with enhanced debugging."""
    try:
        print(f"\n🔍 Searching files with query: '{query}'")
        params = {
            'q': query,
            'pageSize': 100,
            'fields': "files(id, name, mimeType, parents)",
            'includeItemsFromAllDrives': True,
            'supportsAllDrives': True
        }
        if mime_type:
            params['q'] += f" and mimeType='{mime_type}'"
        
        results = drive_service.files().list(**params).execute()
        files = results.get('files', [])
        print(f"📂 Found {len(files)} matching files")
        return files
    except Exception as e:
        print(f"❌ Error searching files: {e}")
        return []

def list_folder_contents(drive_service, folder_id=None, folder_name=None):
    """List all contents of a specific folder with detailed output."""
    try:
        query = f"'{folder_id}' in parents" if folder_id else ""
        if folder_name:
            query += f" and name contains '{folder_name}'"
        
        print(f"\n📂 Listing contents of folder {folder_id or 'root'}:")
        files = search_files(drive_service, query)
        
        if not files:
            print("ℹ️ No files found in this folder")
            return []
            
        print("\n📋 Folder Contents:")
        for i, file in enumerate(files, 1):
            file_type = "📄" if file['mimeType'] != 'application/vnd.google-apps.folder' else "📁"
            print(f"{i}. {file_type} {file['name']} ({file['id']}) [Type: {file['mimeType']}]")
        
        return files
    except Exception as e:
        print(f"❌ Error listing folder contents: {e}")
        return []

def download_pdf(drive_service, file_id, file_name):
    """Download a PDF file with progress tracking."""
    try:
        print(f"\n⬇️ Downloading PDF: {file_name} ({file_id})")
        request = drive_service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            print(f"📥 Download progress: {int(status.progress() * 100)}%")
        
        file.seek(0)
        
        print("📖 Extracting text from PDF...")
        pdf_reader = PyPDF2.PdfReader(file)
        text = ""
        for page_num, page in enumerate(pdf_reader.pages, 1):
            text += page.extract_text() + "\n"
            print(f"📄 Processed page {page_num}")
        
        print(f"✅ Successfully extracted {len(text)} characters")
        return text
    except Exception as e:
        print(f"❌ Error downloading/reading PDF: {e}")
        return None

def process_medical_files(drive_service, folder_id="root"):
    """Process medical history files from Google Drive."""
    try:
        print("\n" + "="*50)
        print("🔎 PROCESSING MEDICAL HISTORY FILES")
        print("="*50)
        
        # First list all contents of the folder for debugging
        list_folder_contents(drive_service, folder_id)
        
        # Search for medical history PDFs
        query = f"name contains 'medical_history_' and '{folder_id}' in parents and mimeType='application/pdf'"
        pdf_files = search_files(drive_service, query)
        
        if not pdf_files:
            print("\n❌ No medical history PDFs found")
            print("ℹ️ Try checking these files:")
            list_folder_contents(drive_service, folder_id)
            return None
        
        print(f"\n🔍 Found {len(pdf_files)} medical history files:")
        for i, file in enumerate(pdf_files, 1):
            print(f"{i}. {file['name']} (ID: {file['id']})")
        
        # Process all files
        all_medical_data = {'students': []}
        
        for file in pdf_files:
            print(f"\n⭐ Processing file: {file['name']}")
            file_content = download_pdf(drive_service, file['id'], file['name'])
            
            if not file_content:
                print(f"❌ Failed to process {file['name']}")
                continue
                
            medical_json = extract_medical_history(file_content)
            
            if medical_json:
                try:
                    medical_data = json.loads(medical_json)
                    all_medical_data['students'].extend(medical_data.get('students', []))
                    print(f"✅ Added {len(medical_data.get('students', []))} student records")
                except json.JSONDecodeError as e:
                    print(f"❌ Error parsing JSON from {file['name']}: {e}")
                except Exception as e:
                    print(f"❌ Error processing {file['name']}: {e}")
        
        if not all_medical_data['students']:
            print("❌ No valid student medical records found")
            return None
            
        print(f"\n🎉 Successfully processed {len(all_medical_data['students'])} student medical records")
        return all_medical_data
        
    except Exception as e:
        print(f"❌ Error processing medical files: {e}")
        return None

# ------------------------
# 🔍 Database Functions
# ------------------------
def get_db_schema(cursor):
    """Introspects the MySQL database to retrieve schema information."""
    schema = ""
    cursor.execute("SHOW TABLES")
    
    tables = []
    fetched_tables = cursor.fetchall()
    if fetched_tables:
        if isinstance(fetched_tables[0], dict):
            db_name = os.getenv('MYSQL_DATABASE', 'SchoolDb')
            tables = [row["Tables_in_" + db_name] for row in fetched_tables]
        else:
            tables = [row[0] for row in fetched_tables]

    for table in tables:
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        columns = cursor.fetchall()
        schema += f"Table: {table}\n"
        
        for column in columns:
            if isinstance(column, dict):
                column_name = column["Field"]
                data_type = column["Type"]
            else:
                column_name = column[0]
                data_type = column[1]
                
            schema += f"- {column_name} ({data_type})\n"
        schema += "\n"
    return schema.strip()

def get_top_math_students(cursor, limit=10):
    """Get top math students from the database."""
    query = """
    SELECT s.student_id, s.first_name, s.last_name, s.email, e.score as math_score
    FROM Students s
    JOIN Enrollments e ON s.student_id = e.student_id
    JOIN Courses c ON e.course_id = c.course_id
    WHERE c.course_name LIKE '%Math%'
    ORDER BY e.score DESC
    LIMIT %s;
    """
    try:
        cursor.execute(query, (limit,))
        return cursor.fetchall()
    except Exception as e:
        print(f"❌ Error fetching math students: {e}")
        return None

# ------------------------
# 🎯 Analysis Functions
# ------------------------
def find_healthiest_top_student(cursor, health_scores):
    """Find the healthiest student among top math performers."""
    if not health_scores:
        print("❌ No health scores available")
        return None
    
    # Get top math students
    math_students = get_top_math_students(cursor)
    if not math_students:
        print("❌ No math students found")
        return None
    
    print(f"\n🔢 Found {len(math_students)} top math students")
    
    # Find students with health data
    results = []
    for student in math_students:
        email = student['email'].lower()
        if email in health_scores:
            results.append({
                'student_id': student['student_id'],
                'name': f"{student['first_name']} {student['last_name']}",
                'email': email,
                'math_score': student['math_score'],
                'health_score': health_scores[email],
                'combined_score': (student['math_score'] * 0.7) + (health_scores[email] * 0.3)
            })
    
    if not results:
        print("❌ No matching students found between DB and medical records")
        return None
    
    # Sort by combined score (70% math, 30% health)
    results.sort(key=lambda x: x['combined_score'], reverse=True)
    return results[0]

# ------------------------
# 🚀 MAIN SCRIPT
# ------------------------
def main():
    # Initialize database connection
    try:
        conn = pymysql.connect(
            host=os.getenv('MYSQL_HOST', 'localhost'),
            port=int(os.getenv('MYSQL_PORT', '3306')),
            user=os.getenv('MYSQL_USER', 'root'),
            password=os.getenv('MYSQL_PASSWORD'),
            database=os.getenv('MYSQL_DATABASE', 'SchoolDb'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        print("✅ MySQL database connection successful.")
    except pymysql.Error as ex:
        print(f"❌ MySQL connection failed: {ex}")
        exit()

    # Initialize Google services
    try:
        GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in .env")

        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        print(f"🤖 Gemini client initialized with model: {GEMINI_MODEL}")
    except Exception as e:
        print(f"❌ Gemini initialization failed: {e}")
        conn.close()
        exit()

    # Initialize Google Drive service
    drive_service = initialize_drive_service()
    if not drive_service:
        conn.close()
        exit()

    # Process medical history files
    DEV_FOLDER_ID = "1kC7xJoCO-RcJpj8R7Rc1B1FXOya_8Ayj"  # Your 'dev' folder
    medical_data = process_medical_files(drive_service, folder_id=DEV_FOLDER_ID)
    
    if not medical_data:
        print("❌ No medical data processed")
        conn.close()
        exit()

    # Calculate health scores
    health_scores = calculate_health_score(medical_data)
    
    # Find the healthiest top math student
    best_student = find_healthiest_top_student(cursor, health_scores)
    
    if best_student:
        print("\n🏆 BEST PERFORMING HEALTHY STUDENT")
        print("="*40)
        print(f"👤 Name: {best_student['name']}")
        print(f"📧 Email: {best_student['email']}")
        print(f"🧮 Math Score: {best_student['math_score']}/100")
        print(f"❤️ Health Score: {best_student['health_score']}/100")
        print(f"⭐ Combined Score: {best_student['combined_score']:.1f}")
        print("="*40)
    else:
        print("❌ Could not determine the best student")

    # Close connection
    conn.close()
    print("✅ Database connection closed")

if __name__ == "__main__":
    main()