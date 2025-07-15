import os
from dotenv import load_dotenv
import google.generativeai as genai

# Import agents
from .agents.database_agent import DatabaseAgent
from .agents.document_agent import DocumentAgent
from .agents.synthesis_agent import SynthesisAgent

# Load environment variables from .env file
load_dotenv()

def main():
    # --- Configuration ---
    # Database config
    db_config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', '3306')),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD'),
        'database': os.getenv('MYSQL_DATABASE', 'SchoolDb')
    }

    # Gemini config
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in .env")
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    print(f"Orchestrator: Gemini client configured with model: {GEMINI_MODEL}")

    # Google Drive Service Account File
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE')
    if not GOOGLE_SERVICE_ACCOUNT_FILE:
        print("Warning: GOOGLE_SERVICE_ACCOUNT_FILE not found in .env. Document agent may not function.")

    # Define the specific folder ID for medical history documents
    # My Google Drive URL: https://drive.google.com/drive/u/0/folders/1kC7xJoCO-RcJpj8R7Rc1B1FXOya_8Ayj
    MEDICAL_HISTORY_FOLDER_ID = "1kC7xJoCO-RcJpj8R7Rc1B1FXOya_8Ayj"

    # --- Initialize Agents ---
    print("\nOrchestrator: Initializing agents...")
    db_agent = DatabaseAgent(db_config, GEMINI_MODEL)
    doc_agent = DocumentAgent(GOOGLE_SERVICE_ACCOUNT_FILE)
    synth_agent = SynthesisAgent(GEMINI_MODEL)

    # --- Connect to DB and Drive ---
    if not db_agent.connect():
        print("Orchestrator: Exiting due to database connection failure.")
        return

    # Attempt to initialize Drive service, but allow continuation if it fails (e.g., no relevant files)
    drive_service_initialized = doc_agent.initialize_drive()

    # --- Get Schema ---
    print("\nOrchestrator: Getting database schema...")
    schema = db_agent.get_schema()
    if not schema:
        print("Orchestrator: Failed to retrieve database schema. Exiting.")
        db_agent.disconnect()
        return
    print("Orchestrator: Schema retrieved successfully.")

    # --- User Question ---
    # The comprehensive user question that drives the entire process
    user_question = "Who is the best student in Calculus I? And what is the latest medical record the student?"
    print(f"\nOrchestrator: User Question: \"{user_question}\"")

    # --- Orchestration Logic ---
    db_results = None
    doc_content = None

    # Step 1: Query DatabaseAgent using the full user_question
    # The DatabaseAgent's LLM will now interpret the entire user_question
    # to generate the necessary SQL for 'top math performers'.
    print("\nOrchestrator: Querying DatabaseAgent based on the full user question...")
    db_results = db_agent.query_database(user_question, schema) # Pass the original user_question

    # Step 2: Get health information from documents
    if drive_service_initialized:
        print("\nOrchestrator: Asking DocumentAgent for student health information...")
        doc_query = "name contains 'medical_history_'"
        doc_content = doc_agent.find_and_extract_text(
            file_query=doc_query,
            mime_type='application/pdf',
            folder_id=MEDICAL_HISTORY_FOLDER_ID
        )
        if doc_content:
            print("Orchestrator: Document content extracted.")
        else:
            print("Orchestrator: No relevant document content found.")
    else:
        print("Orchestrator: DocumentAgent not initialized. Skipping document processing.")


    # Step 3: Synthesize the answer
    print("\nOrchestrator: Passing results to SynthesisAgent for final answer generation...")
    final_answer = synth_agent.synthesize_answer(user_question, db_results, doc_content)

    print("\n--- Final Answer ---")
    print(final_answer)

    # --- Cleanup ---
    db_agent.disconnect()

if __name__ == "__main__":
    main()