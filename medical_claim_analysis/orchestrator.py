# orchestrator.py
import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
import time
import re

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

def main():
    print(f"Orchestrator: Gemini client configured with model: {GEMINI_MODEL}")
    print(f"Orchestrator: API Server URL: {SERVER_URL}")

    # --- Get Authentication Token ---
    auth_token = token_manager.get_token()
    if not auth_token:
        print("Orchestrator: Failed to retrieve authentication token. Exiting.")
        return
    print(f"Orchestrator: Authentication token obtained: {auth_token[:10]}...{auth_token[-10:]}")

    # --- Initialize Agents ---
    print("\nOrchestrator: Initializing agents...")
    policy_agent = PolicyAgent(server_url=SERVER_URL, gemini_model=GEMINI_MODEL, auth_token=auth_token)
    product_agent = ProductAgent(server_url=SERVER_URL, gemini_model=GEMINI_MODEL, auth_token=auth_token)
    synth_agent = SynthesisAgent(GEMINI_MODEL)

    # --- User Question (Example) ---
    user_question = "is policyId 1055970266,F48439136E3684AB1464CFD557C60ACC covered by \"Person Insured\" product?"
    # user_question = "Is policy 1055970266,F48439136E3684AB1464CFD557C60ACC covered Sleep apnea treatment as well?"
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

    # Initialize variables
    policy_response_json = None
    product_response_json = None
    extracted_product_id = None
    is_coverage_element_covered = False

    try:
        # Step 1: Policy Agent - Get policy info and extract product ID
        print(f"\nOrchestrator: PolicyAgent getting info for policyId: {full_policy_id_string}...")
        policy_response_json = policy_agent.fetch_policy_data(full_policy_id_string)
        
        if policy_response_json:
            extracted_product_id = policy_agent.extract_product_id_from_json(policy_response_json)
            if extracted_product_id:
                print(f"Orchestrator: LLM extracted Product ID: {extracted_product_id}")
            else:
                print("Orchestrator: LLM failed to extract Product ID from policy data.")
        else:
            print("Orchestrator: Failed to fetch policy data.")

        # Step 2: Product Agent - Get product info and check coverage
        if extracted_product_id:
            print(f"\nOrchestrator: ProductAgent getting schema for productId: {extracted_product_id}...")
            product_response_json = product_agent.fetch_product_schema_data(extracted_product_id)

            if product_response_json:
                is_coverage_element_covered = product_agent.check_coverage_in_json(
                    product_response_json, target_coverage_element
                )
                print(f"Orchestrator: LLM check: '{target_coverage_element}' covered: {is_coverage_element_covered}")
            else:
                print("Orchestrator: Failed to fetch product schema data.")
        else:
            print("Orchestrator: Product ID not available. Skipping ProductAgent query.")

        # Step 3: Synthesize the answer
        print("\nOrchestrator: Passing results to SynthesisAgent for final answer generation...")
        final_answer = synth_agent.synthesize_answer(
            user_question=user_question,
            policy_data=policy_response_json,
            product_data=product_response_json,
            extracted_product_id=extracted_product_id,
            is_coverage_element_covered=is_coverage_element_covered,
            target_coverage_element=target_coverage_element
        )

        print("\n--- Final Answer ---")
        print(final_answer)

    except Exception as e:
        print(f"\nError during processing: {e}")

if __name__ == "__main__":
    main()