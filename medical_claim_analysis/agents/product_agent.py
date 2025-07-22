# agents/product_agent.py
import requests
import json
import google.generativeai as genai
from typing import Dict, Any, Optional

class ProductAgent:
    def __init__(self, server_url: str, gemini_model: str, auth_token: str):
        self.server_url = server_url
        self.api_base = f"{self.server_url}/api/platform/product/prd/v1"
        self.model = genai.GenerativeModel(gemini_model)
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
        print(f"ProductAgent: Making HTTP request to {endpoint} with product ID: {product_id}")
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print(f"ProductAgent: Failed to parse response as JSON. Response: {response.text[:500]}...")
                    return None
            else:
                print(f"ProductAgent: API returned status {response.status_code}. Response: {response.text[:500]}...")
                return None
        except requests.exceptions.RequestException as e:
            print(f"ProductAgent: Request failed: {e}")
            return None

    def check_coverage_in_json(self, json_data: Dict[str, Any], element_name: str) -> bool:
        """
        Uses the LLM to check if a specific "ProductElementName" exists within
        the product schema JSON data directly.
        """
        if not json_data:
            print("ProductAgent: No JSON data provided for coverage check.")
            return False

        prompt = f"""
        Given the following JSON content representing a product schema, determine if there is an 
        object within the 'productElements' array that has a 'ProductElementName' field with the 
        exact value '{element_name}'. Respond ONLY with 'TRUE' if found, otherwise 'FALSE'.
        Do not include any additional explanation or formatting.

        JSON Data:
        {json.dumps(json_data, indent=2)}
        """
        
        print(f"ProductAgent: Asking LLM to check for '{element_name}' in JSON data")
        try:
            response = self.model.generate_content(prompt, stream=False)
            result = response.text.strip().upper()
            return result == "TRUE"
        except Exception as e:
            print(f"ProductAgent: Error checking coverage with LLM: {e}")
            return False