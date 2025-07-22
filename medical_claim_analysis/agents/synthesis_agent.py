# agents/synthesis_agent.py
import json
import google.generativeai as genai
from typing import Dict, Any, Optional

class SynthesisAgent:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model = genai.GenerativeModel(model_name)

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
        Synthesizes a final answer based on the user's question and the analysis results.
        Now works directly with JSON data instead of file URIs.
        """
        prompt_parts = [
            "You are an intelligent assistant designed to answer questions about insurance policies and products.",
            f"The user's question is: \"{user_question}\"",
            "Here's what I know:\n"
        ]

        # Add policy information
        if policy_data:
            prompt_parts.append("Policy information:")
            prompt_parts.append(json.dumps(policy_data, indent=2))
        else:
            prompt_parts.append("Policy information was not available or could not be processed.")

        # Add product information
        if product_data:
            prompt_parts.append("\nProduct schema information:")
            prompt_parts.append(json.dumps(product_data, indent=2))
        else:
            prompt_parts.append("\nProduct schema information was not available or could not be processed.")

        # Add extracted information
        prompt_parts.append(f"\nFrom the policy data, the Product ID was extracted as: {extracted_product_id if extracted_product_id else 'N/A'}")
        prompt_parts.append(f"Regarding the question about whether the policy is covered by \"{target_coverage_element}\", "
                          f"the analysis indicates: {'YES' if is_coverage_element_covered else 'NO'}")

        # Final instructions
        prompt_parts.append("\nBased on all the provided information, please provide a clear and concise answer to the user's original question. "
                          f"State definitively whether the policy is covered by \"{target_coverage_element}\" and include "
                          "the Policy ID and Product ID if successfully determined. Format your response for easy reading.")

        print("SynthesisAgent: Generating final answer with LLM...")
        try:
            response = self.model.generate_content("\n".join(prompt_parts), stream=False)
            return response.text
        except Exception as e:
            return f"An error occurred while synthesizing the answer: {str(e)}"