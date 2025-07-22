import requests
import json
import google.generativeai as genai
from google.generativeai.protos import FileData # Keep this corrected import
from typing import Dict, Any, Optional

class ProductAgent:
    # REMOVE gemini_client from the __init__ signature
    def __init__(self, server_url: str, gemini_model: str, auth_token: str): # <--- MODIFIED
        self.server_url = server_url
        self.api_base = f"{self.server_url}/api/platform/product/prd/v1"
        self.model = genai.GenerativeModel(gemini_model)
        # REMOVE this line: self.gemini_client = gemini_client
        self.auth_token = auth_token

    def fetch_product_schema_data(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches product schema using the productId from the external API.
        Includes the Authorization header with the bearer token.
        """
        endpoint = f"{self.api_base}/productSchemaByProductId"
        params = {'productId': product_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        print(f"ProductAgent: Making HTTP request to {endpoint} with params {params} and auth header...")
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ProductAgent: Error fetching product schema from external API: {e}")
            return None

    def check_coverage_in_file(self, file_uri: str, element_name: str) -> bool:
        """
        Uses the LLM to check if a specific "ProductElementName" exists within
        the product schema JSON uploaded as a file.
        """
        if not file_uri:
            print("ProductAgent: No file URI provided for coverage check.")
            return False

        prompt = genai.protos.Content(
            parts=[
                genai.protos.Part(text=f"Given the following JSON content representing a product schema, determine if there is an object within the 'productElements' array that has a 'ProductElementName' field with the exact value '{element_name}'. Respond with 'TRUE' if found, otherwise 'FALSE'.\n\nJSON Data:"),
                genai.protos.Part(file_data=genai.protos.FileData(file_uri=file_uri, mime_type="application/json"))
            ]
        )
        
        print(f"ProductAgent: Asking LLM to check for '{element_name}' in file URI: {file_uri}")
        try:
            response = self.model.generate_content(prompt, stream=False)
            result = response.text.strip().upper()
            return result == "TRUE"
        except Exception as e:
            print(f"ProductAgent: Error checking coverage with LLM: {e}")
            return False