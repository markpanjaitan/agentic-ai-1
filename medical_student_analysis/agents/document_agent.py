import os
import io
import PyPDF2
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

class DocumentAgent:
    def __init__(self, service_account_file):
        self.service_account_file = service_account_file
        self.drive_service = None

    def initialize_drive(self):
        """Initialize the Google Drive API service using service account credentials."""
        try:
            if not self.service_account_file or not os.path.exists(self.service_account_file):
                raise ValueError(f"GOOGLE_SERVICE_ACCOUNT_FILE not found or invalid path: {self.service_account_file}")
            
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_file,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            self.drive_service = build('drive', 'v3', credentials=credentials)
            print("DocumentAgent: Google Drive service initialized successfully.")
            return True
        except Exception as e:
            print(f"DocumentAgent: Failed to initialize Google Drive service: {e}")
            self.drive_service = None
            return False

    def search_files(self, query, mime_type=None, folder_id=None): # <--- folder_id parameter added here
        """Search for files in Google Drive matching the query, optionally within a specific folder."""
        if not self.drive_service:
            print("DocumentAgent: Drive service not initialized.")
            return []
        try:
            # Start with the base query
            q_parts = [query]

            if mime_type:
                q_parts.append(f"mimeType='{mime_type}'")
            
            if folder_id: # <--- Logic to include folder_id in query
                q_parts.append(f"'{folder_id}' in parents")
            
            # Combine all parts with 'and'
            full_query = " and ".join(q_parts)

            params = {
                'q': full_query, # <--- Use full_query
                'pageSize': 10,
                'fields': "files(id, name, mimeType)"
            }
            
            results = self.drive_service.files().list(**params).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"DocumentAgent: Error searching files: {e}")
            return []

    def list_root_files(self):
        """List files in the root directory of Google Drive."""
        if not self.drive_service:
            print("DocumentAgent: Drive service not initialized.")
            return []
        try:
            results = self.drive_service.files().list(
                q="'root' in parents and trashed = false",
                pageSize=10,
                fields="files(id, name, mimeType)"
            ).execute()
            return results.get('files', [])
        except Exception as e:
            print(f"DocumentAgent: Error listing root directory files: {e}")
            return []

    def download_pdf(self, file_id):
        """Download a PDF file from Google Drive and extract its text content."""
        if not self.drive_service:
            print("DocumentAgent: Drive service not initialized.")
            return None
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            file = io.BytesIO()
            downloader = MediaIoBaseDownload(file, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file.seek(0)
            
            # Read PDF content
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                extracted_page_text = page.extract_text()
                if extracted_page_text:
                    text += extracted_page_text + "\n"
            
            return text
        except Exception as e:
            print(f"DocumentAgent: Error downloading/reading PDF (File ID: {file_id}): {e}")
            return None

    def find_and_extract_text(self, file_query, mime_type='application/pdf', folder_id=None): # <--- folder_id parameter added here
        """Searches for files and extracts text content from the first matching PDF."""
        print(f"DocumentAgent: Searching for files with query: '{file_query}', MIME type: '{mime_type}', and Folder ID: '{folder_id}'")
        # Pass folder_id to search_files
        files = self.search_files(file_query, mime_type=mime_type, folder_id=folder_id) 
        
        if not files:
            print(f"DocumentAgent: No files found matching your query: '{file_query}' in folder '{folder_id}'.")
            print("DocumentAgent: Listing files in the root directory for debugging (this might not be the target folder):")
            root_files = self.list_root_files()
            if root_files:
                for i, file in enumerate(root_files, 1):
                    print(f"   {i}. {file['name']} (Type: {file['mimeType']}, ID: {file['id']})")
            else:
                print("   No files found in the root directory or error occurred while listing.")
            return None
        
        print(f"DocumentAgent: Found {len(files)} file(s) matching '{file_query}' in folder '{folder_id}':")
        for i, file in enumerate(files, 1):
            print(f"{i}. {file['name']} (ID: {file['id']})")
        
        # For simplicity, process the first file found. Could be expanded to process multiple.
        selected_file = files[0]
        print(f"\nDocumentAgent: Processing file: {selected_file['name']} (ID: {selected_file['id']})")
        
        file_content = self.download_pdf(selected_file['id'])
        if not file_content:
            print("DocumentAgent: Failed to extract content from PDF.")
            return None
        
        return file_content[:2000] # Limit content to avoid excessive token usage downstream