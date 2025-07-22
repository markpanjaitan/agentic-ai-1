# agents/product_agent.py
import requests
import json
import google.generativeai as genai
from google.generativeai.protos import FileData
from typing import Dict, Any, Optional
import time
import tenacity

# Define a retry decorator for the LLM call
@tenacity.retry(
    wait=tenacity.wait_fixed(5),
    stop=tenacity.stop_after_attempt(3),
    retry=tenacity.retry_if_exception_type(Exception) & tenacity.retry_if_exception(
        lambda e: "400 File" in str(e) and "not exist" in str(e)
    ),
    reraise=True
)
def _generate_content_with_retry(model, prompt):
    """Helper function to generate content with retries."""
    return model.generate_content(prompt, stream=False)

class ProductAgent:
    def __init__(self, server_url: str, gemini_model: str, auth_token: str):
        self.server_url = server_url
        self.api_base = f"{self.server_url}/api/platform/product/prd/v1"
        self.model = genai.GenerativeModel(gemini_model)
        self.auth_token = auth_token

    def fetch_product_schema_data(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches product schema information using the productId string from the external API.
        Includes the Authorization header with the bearer token.
        """
        endpoint = f"{self.api_base}/loadSchemaById"
        params = {'id': product_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        print(f"ProductAgent: Making HTTP request to {endpoint} with params {params} and auth header...")
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            
            print(f"ProductAgent: API Response Status Code: {response.status_code}")

            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print(f"ProductAgent: JSONDecodeError: Failed to parse response as JSON. Response text: {response.text[:500]}...")
                    return None
            else:
                print(f"ProductAgent: Non-200 Status Code. Response text: {response.text[:500]}...")
                response.raise_for_status()
                return None
        except requests.exceptions.RequestException as e:
            print(f"ProductAgent: Error fetching product schema info from external API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"ProductAgent: Detailed error response (if available): {e.response.text[:500]}...")
            return None
        except Exception as e:
            print(f"ProductAgent: An unexpected error occurred: {e}")
            return None

    def check_coverage_in_file(self, file_uri: str, target_coverage_element: str) -> bool:
        """
        Uses the LLM to check if the target coverage element is present and active
        in the uploaded product schema file.
        """
        if not file_uri:
            print("ProductAgent: No file URI provided for coverage check.")
            return False

        prompt = genai.protos.Content(
            parts=[
                genai.protos.Part(text=f"Given the following JSON content from a product schema, determine if the coverage element '{target_coverage_element}' is present and active. Respond only with 'True' or 'False'.\n\nJSON Data:"),
                genai.protos.Part(file_data=genai.protos.FileData(file_uri=file_uri, mime_type="text/plain"))
            ]
        )
        
        print(f"ProductAgent: Asking LLM to check coverage for '{target_coverage_element}' in file URI: {file_uri}")
        try:
            time.sleep(3) # Increased wait time before LLM call
            response = _generate_content_with_retry(self.model, prompt)
            result = response.text.strip().lower()
            return result == "true"
        except Exception as e:
            print(f"ProductAgent: Error checking coverage with LLM: {e}")
            return False