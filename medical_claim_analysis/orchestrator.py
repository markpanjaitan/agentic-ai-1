import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.protos import FileData # Keep this corrected import
import time # For unique filenames
import re # Import regex module for more robust extraction

# Import agents
from agents.policy_agent import PolicyAgent
from agents.product_agent import ProductAgent
from agents.synthesis_agent import SynthesisAgent

# Import configuration and utility
from config import SERVER_URL, GEMINI_API_KEY, GEMINI_MODEL
from utils.token_manager import token_manager # Import the singleton instance

# Configure Gemini
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")
genai.configure(api_key=GEMINI_API_KEY)

# We no longer initialize a 'gemini_client' attribute
# gemini_client = genai.Client(api_key=GEMINI_API_KEY) # <--- REMOVE THIS LINE

def upload_to_gemini(filepath: str, mime_type: str) -> FileData:
    """Uploads a file to Gemini's Files API and returns the FileData."""
    print(f"Uploading {filepath} to Gemini Files API...")
    try:
        # Use genai.upload_file directly
        file = genai.upload_file(
            path=filepath, # Note: It's 'path' not 'file_path' for genai.upload_file
            display_name=os.path.basename(filepath) # Optional: set a display name
        )
        print(f"Uploaded file '{file.display_name}' as: {file.uri}")
        # The file object returned by genai.upload_file should already be "READY" or
        # handle internal polling. Explicit polling is often not needed for simple upload.
        # If issues arise, you might re-introduce the polling logic, but start simpler.
        
        # For robustness, we can add a basic check if the file object indicates state.
        # However, genai.upload_file generally handles waiting for READY internally.
        # If your version of genai.upload_file doesn't block, you might need this:
        # while file.state.name == "PROCESSING":
        #     print(".", end="", flush=True)
        #     time.sleep(1)
        #     file = genai.get_file(file.name) # Use genai.get_file directly
        # if file.state.name == "READY":
        #     print(f"\nFile {file.display_name} is READY.")
        #     return file
        # else:
        #     raise Exception(f"File upload failed with state: {file.state.name}")
        
        return file # Return the file object directly

    except Exception as e:
        print(f"Error uploading file {filepath}: {e}")
        raise

def delete_from_gemini(file_name: str):
    """Deletes a file from Gemini's Files API."""
    print(f"Deleting file {file_name} from Gemini Files API...")
    try:
        # Use genai.delete_file directly
        genai.delete_file(name=file_name)
        print(f"File {file_name} deleted successfully.")
    except Exception as e:
        print(f"Error deleting file {file_name}: {e}")

def main():
    print(f"Orchestrator: Gemini client configured with model: {GEMINI_MODEL}")
    print(f"Orchestrator: API Server URL: {SERVER_URL}")

    # --- Get Authentication Token ---
    auth_token = token_manager.get_token()
    if not auth_token:
        print("Orchestrator: Failed to retrieve authentication token. Exiting.")
        return
    print(f"Orchestrator: Authentication token obtained: {auth_token[:10]}...{auth_token[-10:]}") # Partial print for security

    # --- Initialize Agents ---
    print("\nOrchestrator: Initializing agents...")
    # REMOVE gemini_client from agent initialization as it's no longer a class
    policy_agent = PolicyAgent(server_url=SERVER_URL, gemini_model=GEMINI_MODEL, auth_token=auth_token)
    product_agent = ProductAgent(server_url=SERVER_URL, gemini_model=GEMINI_MODEL, auth_token=auth_token)
    synth_agent = SynthesisAgent(GEMINI_MODEL)

    # --- User Question (Example) ---
    user_question = "is policyId 1055970266,F48439136E3684AB1464CFD557C60ACC covered by \"Person Insured\" product?"
    print(f"\nOrchestrator: User Question: \"{user_question}\"")

    # Extract the full composite policyId string
    policy_id_match = re.search(r"policyId\s+([a-zA-Z0-9,]+)", user_question)
    full_policy_id_string = policy_id_match.group(1).strip() if policy_id_match else None

    if not full_policy_id_string:
        print("Orchestrator: Could not extract policy ID from the question. Exiting.")
        return

    # Extract the target coverage element
    coverage_element_match = re.search(r"covered by\s+\"([^\"]+)\"|\"([^\"]+)\"\?", user_question)
    if coverage_element_match:
        if coverage_element_match.group(1):
            target_coverage_element = coverage_element_match.group(1).strip()
        elif coverage_element_match.group(2):
            target_coverage_element = coverage_element_match.group(2).strip()
        else:
            target_coverage_element = None
    else:
        target_coverage_element = None

    if not target_coverage_element:
        print("Orchestrator: Could not extract target coverage element from the question. Exiting.")
        return

    print(f"Orchestrator: Extracted Policy ID: {full_policy_id_string}")
    print(f"Orchestrator: Extracted Target Coverage Element: \"{target_coverage_element}\"")

    # --- Orchestration Logic ---
    policy_file_data = None
    product_file_data = None
    extracted_product_id = None
    is_coverage_element_covered = False

    try:
        # Step 1: Policy Agent - Get policy info, save, upload, and LLM extracts product ID
        print(f"\nOrchestrator: PolicyAgent getting info for policyId: {full_policy_id_string}...")
        policy_response_json = policy_agent.fetch_policy_data(full_policy_id_string)
        
        if policy_response_json:
            policy_filepath = f"temp_policy_response_{int(time.time())}.json"
            with open(policy_filepath, 'w') as f:
                json.dump(policy_response_json, f, indent=2)
            print(f"Orchestrator: Policy response saved to {policy_filepath}")

            policy_file_data = upload_to_gemini(policy_filepath, "application/json")
            
            extracted_product_id = policy_agent.extract_product_id_from_file(policy_file_data.uri)
            if extracted_product_id:
                print(f"Orchestrator: LLM extracted Product ID: {extracted_product_id}")
            else:
                print("Orchestrator: LLM failed to extract Product ID from policy data.")
        else:
            print("Orchestrator: Failed to fetch policy data.")

        # Step 2: Product Agent - Get product info, save, upload, and LLM checks coverage
        if extracted_product_id:
            print(f"\nOrchestrator: ProductAgent getting schema for productId: {extracted_product_id}...")
            product_response_json = product_agent.fetch_product_schema_data(extracted_product_id)

            if product_response_json:
                product_filepath = f"temp_product_response_{int(time.time())}.json"
                with open(product_filepath, 'w') as f:
                    json.dump(product_response_json, f, indent=2)
                print(f"Orchestrator: Product response saved to {product_filepath}")

                product_file_data = upload_to_gemini(product_filepath, "application/json")

                is_coverage_element_covered = product_agent.check_coverage_in_file(
                    product_file_data.uri, target_coverage_element
                )
                print(f"Orchestrator: LLM check: '{target_coverage_element}' covered: {is_coverage_element_covered}")
            else:
                print("Orchestrator: Failed to fetch product schema data.")
        else:
            print("Orchestrator: Product ID not available. Skipping ProductAgent query.")

        # Step 3: Synthesize the answer
        print("\nOrchestrator: Passing results to SynthesisAgent for final answer generation...")
        final_answer = synth_agent.synthesize_answer_with_files(
            user_question=user_question,
            policy_file_uri=policy_file_data.uri if policy_file_data else None,
            product_file_uri=product_file_data.uri if product_file_data else None,
            extracted_product_id=extracted_product_id,
            is_coverage_element_covered=is_coverage_element_covered,
            target_coverage_element=target_coverage_element
        )

        print("\n--- Final Answer ---")
        print(final_answer)

    finally:
        if 'policy_filepath' in locals() and os.path.exists(policy_filepath):
            os.remove(policy_filepath)
        if policy_file_data:
            delete_from_gemini(policy_file_data.name)
        
        if 'product_filepath' in locals() and os.path.exists(product_filepath):
            os.remove(product_filepath)
        if product_file_data:
            delete_from_gemini(product_file_data.name)
            
        print("\nOrchestrator: Cleanup complete.")

if __name__ == "__main__":
    main()