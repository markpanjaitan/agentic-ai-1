# agents/policy_agent.py
import requests
import json
import google.generativeai as genai
from typing import Dict, Any, Optional

class PolicyAgent:
    def __init__(self, server_url: str, gemini_model: str, auth_token: str):
        self.server_url = server_url
        self.api_base = f"{self.server_url}/api/platform/proposal/core/proposal/v1"
        self.model = genai.GenerativeModel(gemini_model)
        self.auth_token = auth_token

    def fetch_policy_data(self, composite_policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches policy information using the composite policyId string from the external API.
        """
        endpoint = f"{self.api_base}/loadWithPlanDetail"
        params = {'policyId': composite_policy_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"PolicyAgent: Making HTTP request to {endpoint} with policy ID: {composite_policy_id}")
        try:
            response = requests.get(endpoint, params=params, headers=headers)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print(f"PolicyAgent: Failed to parse response as JSON. Response: {response.text[:500]}...")
                    return None
            else:
                print(f"PolicyAgent: API returned status {response.status_code}. Response: {response.text[:500]}...")
                return None
        except requests.exceptions.RequestException as e:
            print(f"PolicyAgent: Request failed: {e}")
            return None

    def extract_product_id_from_json(self, json_data: dict) -> Optional[str]:
        """
        Uses the LLM to extract the productId directly from JSON data.
        """
        if not json_data:
            print("PolicyAgent: No JSON data provided for product ID extraction.")
            return None

        prompt = f"""
        Given the following JSON content from a policy API response, extract ONLY the value of the 'productId' field 
        from the 'body' object. Return ONLY the productId value or 'NOT_FOUND' if it doesn't exist.
        Do not include any additional explanation or formatting.

        JSON Data:
        {json.dumps(json_data, indent=2)}
        """
        
        print("PolicyAgent: Asking LLM to extract product ID from JSON data...")
        try:
            response = self.model.generate_content(prompt, stream=False)
            product_id = response.text.strip()
            return product_id if product_id != "NOT_FOUND" else None
        except Exception as e:
            print(f"PolicyAgent: Error extracting product ID: {e}")
            return None