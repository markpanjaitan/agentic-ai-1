# agents/synthesis_agent.py
import google.generativeai as genai
from google.generativeai.protos import FileData
from typing import Dict, Any, Optional

class SynthesisAgent:
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model = genai.GenerativeModel(model_name)

    def synthesize_answer_with_files(
        self,
        user_question: str,
        policy_file_uri: Optional[str],
        product_file_uri: Optional[str],
        extracted_product_id: Optional[str],
        is_coverage_element_covered: bool, # Renamed variable
        target_coverage_element: str # New parameter
    ) -> str:
        """
        Synthesizes a final answer based on the user's question and the results
        derived from the file analysis by the LLM.
        """
        parts = [
            genai.protos.Part(text=f"You are an intelligent assistant designed to answer questions about insurance policies and products."),
            genai.protos.Part(text=f"The user's question is: \"{user_question}\""),
            genai.protos.Part(text=f"Here's what I know:\n")
        ]

        if policy_file_uri:
            parts.append(genai.protos.Part(text=f"I have analyzed the policy information from the following file (policy_data.json):"))
            parts.append(genai.protos.Part(file_data=genai.protos.FileData(file_uri=policy_file_uri, mime_type="application/json")))
        else:
            parts.append(genai.protos.Part(text="Policy information was not available or could not be processed."))

        if product_file_uri:
            parts.append(genai.protos.Part(text=f"\nI have analyzed the product schema information from the following file (product_schema.json):"))
            parts.append(genai.protos.Part(file_data=genai.protos.FileData(file_uri=product_file_uri, mime_type="application/json")))
        else:
            parts.append(genai.protos.Part(text="Product schema information was not available or could not be processed."))

        parts.append(genai.protos.Part(text=f"\nFrom the policy data, the Product ID was extracted as: {extracted_product_id if extracted_product_id else 'N/A'}"))
        
        # IMPORTANT: The prompt now uses the dynamic `target_coverage_element` and renamed boolean
        parts.append(genai.protos.Part(text=f"Regarding the question about whether the policy is covered by \"{target_coverage_element}\", the analysis of the product schema indicates: {is_coverage_element_covered}"))

        parts.append(genai.protos.Part(text=f"\nBased on all the provided information, please provide a clear and concise answer to the user's original question. State definitively whether the policy is covered by \"{target_coverage_element}\" and include the Policy ID and Product ID if successfully determined."))

        print("SynthesisAgent: Generating final answer with LLM, referencing uploaded files...")
        try:
            response = self.model.generate_content(parts, stream=False)
            return response.text
        except Exception as e:
            return f"SynthesisAgent: Error generating final answer: {e}"