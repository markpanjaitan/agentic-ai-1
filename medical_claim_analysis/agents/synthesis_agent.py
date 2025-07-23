# agents/synthesis_agent.py
import json
import google.generativeai as genai
from typing import Dict, Any, Optional

class SynthesisAgent:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model = genai.GenerativeModel(
            model_name,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 1000,
                "top_p": 0.95
            }
        )

    def synthesize_answer(
        self,
        user_question: str,
        policy_data: Optional[Dict[str, Any]],
        product_data: Optional[Dict[str, Any]],
        extracted_product_id: Optional[str],
        is_coverage_element_covered: bool,
        target_coverage_element: str
    ) -> str:
        """
        Enhanced answer synthesis with:
        - Structured response format
        - Better context handling
        - Error resilience
        - Professional tone
        """
        try:
            # Prepare the structured prompt
            prompt = self._build_prompt(
                user_question,
                policy_data,
                product_data,
                extracted_product_id,
                is_coverage_element_covered,
                target_coverage_element
            )
            
            print("[SynthesisAgent] Generating final response...")
            response = self.model.generate_content(prompt)
            
            if not response.text:
                raise ValueError("Empty response from model")
                
            return self._format_response(response.text)
            
        except Exception as e:
            error_msg = f"[SynthesisAgent] Error: {str(e)}"
            print(error_msg)
            return self._build_error_response(user_question, error_msg)

    def _build_prompt(
        self,
        user_question: str,
        policy_data: Optional[Dict[str, Any]],
        product_data: Optional[Dict[str, Any]],
        product_id: Optional[str],
        is_covered: bool,
        coverage_element: str
    ) -> str:
        """Constructs a detailed, structured prompt for the LLM"""
        return f"""
        **Insurance Policy Analysis Task**

        **User Question**: "{user_question}"

        **Policy Details**:
        {self._format_data(policy_data, "Policy")}

        **Product Details**:
        {self._format_data(product_data, "Product")}

        **Key Findings**:
        - Product ID: {product_id or "Not available"}
        - Coverage for "{coverage_element}": {"Covered" if is_covered else "Not covered"}
        
        **Response Requirements**:
        1. Address the user's question directly in the opening sentence
        2. Provide a definitive yes/no answer about coverage
        3. Include relevant policy and product identifiers
        4. Explain the basis for your conclusion
        5. Use professional but approachable language
        6. Format with clear paragraphs and bullet points when helpful
        
        **Example Structure**:
        "Based on our analysis of policy [ID] and product [ID], [coverage element] is [covered/not covered]. 
        This determination was made because...[explanation]."
        """

    def _format_data(self, data: Optional[Dict[str, Any]], data_type: str) -> str:
        """Formats JSON data for inclusion in prompt"""
        if not data:
            return f"{data_type} data not available"
            
        try:
            return f"{data_type} Data:\n{json.dumps(data, indent=2)}"
        except:
            return f"{data_type} data (formatting error)"

    def _format_response(self, raw_response: str) -> str:
        """Ensures consistent response formatting"""
        return f"""
        === Coverage Determination ===
        {raw_response.strip()}
        
        Note: This is an automated analysis. For official confirmation, 
        please consult your policy documents or agent.
        """

    def _build_error_response(self, question: str, error: str) -> str:
        """Creates user-friendly error messages"""
        return f"""
        We encountered an issue processing your question about:
        "{question}"
        
        Error: {error}
        
        Please try again or contact support if the issue persists.
        """