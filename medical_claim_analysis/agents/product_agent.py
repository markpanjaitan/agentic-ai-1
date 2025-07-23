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
        Fetches product schema data from API
        """
        endpoint = f"{self.api_base}/productSchemaByProductId"
        params = {'productId': product_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                endpoint,
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"\n[DEBUG] API Request Failed - Status: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"\n[DEBUG] Request Exception: {str(e)}")
            return None

    def check_coverage_in_json(self, user_question: str, json_data: Dict[str, Any], coverage_element: str) -> bool:
        """
        Checks if coverage element exists in product data
        """
        if not json_data:
            print("\n[DEBUG] No JSON data provided for coverage check")
            return False

        prompt = f"""
        **Task**: Determine if '{coverage_element}' is covered based on:
        - User Question: "{user_question}"
        - Full Product Data: {json.dumps(json_data, indent=2)}
        """
        
        # print(f"\n[DEBUG] Coverage Check Prompt:\n{prompt}")
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 10
                }
            )
            
            print(f"\n[DEBUG] LLM Raw Response:\n{response.text}")
            
            result = response.text.strip().upper()
            
            if result not in ["TRUE", "FALSE"]:
                print(f"\n[DEBUG] Unexpected LLM Response Format: {result}")
                return False
                
            print(f"\n[DEBUG] Final Coverage Determination: {result}")
            return result == "TRUE"
            
        except Exception as e:
            print(f"\n[DEBUG] LLM Processing Error: {str(e)}")
            return False