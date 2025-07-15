from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import PyPDF2
import google.generativeai as genai
from ..config import Config

genai.configure(api_key=Config.GEMINI_API_KEY)

class MedicalAgent:
    def __init__(self):
        self.drive_service = self._initialize_drive_service()
    
    def _initialize_drive_service(self):
        """Initialize Google Drive service"""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                Config.SERVICE_ACCOUNT_FILE,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            print(f"Drive service init failed: {e}")
            return None
    
    def _download_and_extract_pdf(self, file_id):
        """Download and extract text from PDF"""
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            fh.seek(0)
            pdf_reader = PyPDF2.PdfReader(fh)
            return "\n".join(page.extract_text() for page in pdf_reader.pages)
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            return None
    
    def _extract_medical_history(self, text):
        """Extract medical history from text using LLM"""
        model = genai.GenerativeModel(Config.GEMINI_MODEL)
        prompt = f"""Extract medical history from this text and return as JSON:
{text[:10000]}"""
        response = model.generate_content(prompt)
        try:
            return eval(response.text)  # Simple parsing - use json.loads in production
        except:
            return None
    
    def get_health_scores(self):
        """Process medical files and return health scores"""
        if not self.drive_service:
            return None
            
        try:
            query = f"name contains 'medical_history_' and '{Config.DRIVE_FOLDER_ID}' in parents and mimeType='application/pdf'"
            results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            
            all_data = {'students': []}
            for file in files:
                text = self._download_and_extract_pdf(file['id'])
                if text:
                    medical_data = self._extract_medical_history(text)
                    if medical_data:
                        all_data['students'].extend(medical_data.get('students', []))
            return self._calculate_health_scores(all_data) if all_data['students'] else None
        except Exception as e:
            print(f"Error processing medical files: {e}")
            return None
    
    @staticmethod
    def _calculate_health_scores(medical_data):
        """Calculate health scores from medical data"""
        health_scores = {}
        for student in medical_data.get('students', []):
            score = 100
            # Deduct points based on medical conditions
            for condition in student.get('conditions', []):
                severity_map = {'mild': 5, 'moderate': 15, 'severe': 30}
                score -= severity_map.get(condition.get('severity', 'mild'), 5)
                if condition.get('chronic', False):
                    score -= 10
            score -= len(student.get('allergies', [])) * 3
            score -= len(student.get('current_medications', [])) * 2
            health_scores[student['email'].lower()] = max(0, score)
        return health_scores