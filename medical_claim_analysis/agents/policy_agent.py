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
        Returns:
            Dict[str, Any]: Policy data if successful
            None: If request fails
        """
        endpoint = f"{self.api_base}/loadWithPlanDetail"
        params = {'policyId': composite_policy_id}
        headers = {
            'Authorization': f'Bearer {self.auth_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"[PolicyAgent] Fetching policy data for ID: {composite_policy_id}")
        try:
            response = requests.get(
                endpoint, 
                params=params, 
                headers=headers,
                timeout=10  # Added timeout
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print("[PolicyAgent] Successfully fetched policy data")
                    return data
                except json.JSONDecodeError:
                    print(f"[PolicyAgent] Error: Invalid JSON response. Status: {response.status_code}")
                    return None
            print(f"[PolicyAgent] Error: API returned {response.status_code}. Response: {response.text[:200]}...")
            return None
            
        except requests.exceptions.RequestException as e:
            print(f"[PolicyAgent] Request failed: {str(e)}")
            return None

    def extract_product_id_from_json(self, user_question: str, json_data: dict) -> Optional[str]:
        """
        Enhanced version that uses the user question for better context.
        Returns:
            str: Extracted product ID
            None: If extraction fails
        """
        if not json_data:
            print("[PolicyAgent] Error: No JSON data provided")
            return None

        prompt = f"""
        **Task**: Extract the productId from this policy data to answer the user's question.
        
        **User Question**: "{user_question}"
        
        **Policy Data**:
        {json.dumps(json_data, indent=2)}
        
        **Instructions**:
        1. Locate the 'productId' field in the 'body' object
        2. Return ONLY the productId value
        3. If not found, return 'NOT_FOUND'
        
        **Output Format**: 
        <productId_value_or_NOT_FOUND>
        """
        
        print("[PolicyAgent] Extracting product ID with LLM...")
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,  # More deterministic
                    "max_output_tokens": 50
                }
            )
            product_id = response.text.strip()
            
            if product_id == "NOT_FOUND":
                print("[PolicyAgent] Product ID not found in policy data")
                return None
                
            print(f"[PolicyAgent] Extracted Product ID: {product_id}")
            return product_id
            
        except Exception as e:
            print(f"[PolicyAgent] Extraction failed: {str(e)}")
            return None