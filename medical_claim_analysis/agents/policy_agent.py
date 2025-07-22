import requests
import json
import google.generativeai as genai
from google.generativeai.protos import FileData # Keep this corrected import
from typing import Dict, Any, Optional

class PolicyAgent:
    # REMOVE gemini_client from the __init__ signature
    def __init__(self, server_url: str, gemini_model: str, auth_token: str): # <--- MODIFIED
        self.server_url = server_url
        self.api_base = f"{self.server_url}/api/platform/proposal/core/proposal/v1"
        self.model = genai.GenerativeModel(gemini_model)
        # REMOVE this line: self.gemini_client = gemini_client
        self.auth_token = auth_token # Store the token

    def fetch_policy_data(self, composite_policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches policy information using the composite policyId string from the external API.
        Includes the Authorization header with the bearer token.
        """
        endpoint = f"{self.api_base}/loadWithPlanDetail"
        params = {'policyId': composite_policy_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json' # Always good to explicitly set for JSON APIs
        }
        print(f"PolicyAgent: Making HTTP request to {endpoint} with params {params} and auth header...")
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"PolicyAgent: Error fetching policy info from external API: {e}")
            return None

    def extract_product_id_from_file(self, file_uri: str) -> Optional[str]:
        """
        Uses the LLM to extract the productId from an uploaded policy response file.
        """
        if not file_uri:
            print("PolicyAgent: No file URI provided for product ID extraction.")
            return None

        prompt = genai.protos.Content(
            parts=[
                genai.protos.Part(text="Given the following JSON content from a policy API response, extract ONLY the value of the 'productId' field from the 'body' object. If 'productId' is not found or 'body' is missing, state 'NOT_FOUND'.\n\nJSON Data:"),
                genai.protos.Part(file_data=genai.protos.FileData(file_uri=file_uri, mime_type="application/json"))
            ]
        )
        
        print(f"PolicyAgent: Asking LLM to extract product ID from file URI: {file_uri}")
        try:
            response = self.model.generate_content(prompt, stream=False)
            product_id = response.text.strip()
            if product_id == "NOT_FOUND":
                return None
            return product_id
        except Exception as e:
            print(f"PolicyAgent: Error extracting product ID with LLM: {e}")
            return None