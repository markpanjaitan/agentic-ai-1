# agents/policy_agent.py
import requests
import json
import google.generativeai as genai
from google.generativeai.protos import FileData
from typing import Dict, Any, Optional
import time
import tenacity

# Define a retry decorator for the LLM call
@tenacity.retry(
    wait=tenacity.wait_fixed(5),  # Wait 5 seconds between retries
    stop=tenacity.stop_after_attempt(3), # Try up to 3 times
    retry=tenacity.retry_if_exception_type(Exception) & tenacity.retry_if_exception(
        lambda e: "400 File" in str(e) and "not exist" in str(e)
    ),
    reraise=True # Re-raise the exception if all retries fail
)
def _generate_content_with_retry(model, prompt):
    """Helper function to generate content with retries."""
    return model.generate_content(prompt, stream=False)

class PolicyAgent:
    def __init__(self, server_url: str, gemini_model: str, auth_token: str):
        self.server_url = server_url
        self.api_base = f"{self.server_url}/api/platform/proposal/core/proposal/v1"
        self.model = genai.GenerativeModel(gemini_model)
        self.auth_token = auth_token

    def fetch_policy_data(self, composite_policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches policy information using the composite policyId string from the external API.
        Includes the Authorization header with the bearer token.
        """
        endpoint = f"{self.api_base}/loadWithPlanDetail"
        params = {'policyId': composite_policy_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        print(f"PolicyAgent: Making HTTP request to {endpoint} with params {params} and auth header...")
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            
            print(f"PolicyAgent: API Response Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print(f"PolicyAgent: JSONDecodeError: Failed to parse response as JSON. Response text: {response.text[:500]}...")
                    return None
            else:
                print(f"PolicyAgent: Non-200 Status Code. Response text: {response.text[:500]}...")
                response.raise_for_status() # This will raise an HTTPError for 4xx/5xx responses
                return None # Should not be reached if raise_for_status() raises
        except requests.exceptions.RequestException as e:
            print(f"PolicyAgent: Error fetching policy info from external API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"PolicyAgent: Detailed error response (if available): {e.response.text[:500]}...")
            return None
        except Exception as e: # Catch any other unexpected errors during the process
            print(f"PolicyAgent: An unexpected error occurred: {e}")
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
                genai.protos.Part(file_data=genai.protos.FileData(file_uri=file_uri, mime_type="text/plain"))
            ]
        )
        
        print(f"PolicyAgent: Asking LLM to extract product ID from file URI: {file_uri}")
        try:
            time.sleep(3) # Increased wait time before LLM call
            response = _generate_content_with_retry(self.model, prompt)
            product_id = response.text.strip()
            if product_id == "NOT_FOUND":
                return None
            return product_id
        except Exception as e:
            print(f"PolicyAgent: Error extracting product ID with LLM: {e}")
            return None