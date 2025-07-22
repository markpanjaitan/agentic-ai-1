# orchestrator.py
import os
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Optional

# Import agents
from agents.policy_agent import PolicyAgent
from agents.product_agent import ProductAgent
from agents.synthesis_agent import SynthesisAgent

# Import configuration and utility
from config import SERVER_URL, GEMINI_API_KEY, GEMINI_MODEL
from utils.token_manager import token_manager

# Configure Gemini
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env")
genai.configure(api_key=GEMINI_API_KEY)

def extract_policy_info(user_question: str) -> tuple[Optional[str], Optional[str]]:
    """
    Improved extraction of policy ID and coverage element from natural language questions.
    Returns tuple of (policy_id, coverage_element)
    """
    # More flexible policy ID matching
    policy_pattern = r"(?:policy|policy\s*id|policy\s*ID|Policy)\s*:?\s*([a-zA-Z0-9,]+)"
    policy_match = re.search(policy_pattern, user_question, re.IGNORECASE)
    policy_id = policy_match.group(1).strip() if policy_match else None

    # More flexible coverage element matching
    coverage_pattern = r"(?:covered|cover|coverage|includes)\s+(?:by\s+)?[\"']?([^\"'\?]+)[\"']?"
    coverage_match = re.search(coverage_pattern, user_question, re.IGNORECASE)
    coverage_element = coverage_match.group(1).strip() if coverage_match else None

    return policy_id, coverage_element

def main():
    print(f"Orchestrator: Gemini client configured with model: {GEMINI_MODEL}")
    print(f"Orchestrator: API Server URL: {SERVER_URL}")

    # Get Authentication Token
    auth_token = token_manager.get_token()
    if not auth_token:
        print("Orchestrator: Failed to retrieve authentication token. Exiting.")
        return
    print(f"Orchestrator: Authentication token obtained: {auth_token[:10]}...{auth_token[-10:]}")

    # Initialize Agents
    print("\nOrchestrator: Initializing agents...")
    policy_agent = PolicyAgent(server_url=SERVER_URL, gemini_model=GEMINI_MODEL, auth_token=auth_token)
    product_agent = ProductAgent(server_url=SERVER_URL, gemini_model=GEMINI_MODEL, auth_token=auth_token)
    synth_agent = SynthesisAgent(GEMINI_MODEL)

    # User Question (with more natural language examples)
    # user_question = "Is policy 1055970266,F48439136E3684AB1464CFD557C60ACC covered for Sleep apnea treatment?"
    user_question = "Is policy 1055970266,F48439136E3684AB1464CFD557C60ACC covered for Person Insured?"

    print(f"\n{'='*50}\nOrchestrator: Processing Question: \"{user_question}\"")

    # Extract policy info using improved NLP
    full_policy_id_string, target_coverage_element = extract_policy_info(user_question)
    
    if not full_policy_id_string:
        print("Orchestrator: Could not extract policy ID from the question.")
        return
        
    if not target_coverage_element:
        print("Orchestrator: Could not extract coverage element from the question.")
        target_coverage_element = "the requested coverage"  # Default fallback

    print(f"Orchestrator: Extracted Policy ID: {full_policy_id_string}")
    print(f"Orchestrator: Extracted Coverage Element: \"{target_coverage_element}\"")

    try:
        # Step 1: Get policy info
        print(f"\nOrchestrator: Fetching policy info...")
        policy_response = policy_agent.fetch_policy_data(full_policy_id_string)
        
        if not policy_response:
            print("Orchestrator: Failed to fetch policy data.")
            return

        # Step 2: Extract product ID
        print("Orchestrator: Extracting product ID...")
        product_id = policy_agent.extract_product_id_from_json(
            user_question=user_question,
            json_data=policy_response
        )
        
        if not product_id:
            print("Orchestrator: Failed to extract product ID.")
            return
        print(f"Orchestrator: Product ID: {product_id}")

        # Step 3: Get product data
        product_schema = product_agent.fetch_product_schema_data(product_id)
        if not product_schema:
            print("Orchestrator: Failed to fetch product data.")
            return

        # Step 4: Check coverage
        is_covered = product_agent.check_coverage_in_json(
            user_question=user_question,
            json_data=product_schema,
            coverage_element=target_coverage_element
        )

        # Step 5: Generate final answer
        print("\nOrchestrator: Generating final answer...")
        final_answer = synth_agent.synthesize_answer(
            user_question=user_question,
            policy_data=policy_response,
            product_data=product_schema,
            extracted_product_id=product_id,
            is_coverage_element_covered=is_covered,
            target_coverage_element=target_coverage_element
        )

        print("\n--- Final Answer ---")
        print(final_answer)
        print(f"\n{'='*50}")

    except Exception as e:
        print(f"\nError during processing: {str(e)}")

if __name__ == "__main__":
    main()