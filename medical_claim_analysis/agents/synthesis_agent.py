# agents/synthesis_agent.py
import google.generativeai as genai
from google.generativeai.protos import FileData
from typing import Optional
import time # New import
import tenacity # New import

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


class SynthesisAgent:
    def __init__(self, gemini_model: str):
        self.model = genai.GenerativeModel(gemini_model)

    def synthesize_answer_with_files(self, 
                                     user_question: str,
                                     policy_file_uri: Optional[str],
                                     product_file_uri: Optional[str],
                                     extracted_product_id: Optional[str],
                                     is_coverage_element_covered: bool,
                                     target_coverage_element: str) -> str:
        
        prompt_parts = [
            genai.protos.Part(text=f"Based on the following information and files, answer the user's question concisely."),
            genai.protos.Part(text=f"User's Question: '{user_question}'"),
            genai.protos.Part(text=f"Extracted Policy ID from question: {extracted_product_id if extracted_product_id else 'N/A'}"),
            genai.protos.Part(text=f"Target coverage element: '{target_coverage_element}'"),
            genai.protos.Part(text=f"LLM analysis result for coverage: {is_coverage_element_covered}"),
            genai.protos.Part(text="\n--- Relevant Data ---\n")
        ]

        if policy_file_uri:
            prompt_parts.append(genai.protos.Part(text="Policy Data (uploaded file):"))
            prompt_parts.append(genai.protos.Part(file_data=genai.protos.FileData(file_uri=policy_file_uri, mime_type="text/plain")))
        else:
            prompt_parts.append(genai.protos.Part(text="Policy Data: Not available."))
        
        if product_file_uri:
            prompt_parts.append(genai.protos.Part(text="Product Schema Data (uploaded file):"))
            prompt_parts.append(genai.protos.Part(file_data=genai.protos.FileData(file_uri=product_file_uri, mime_type="text/plain")))
        else:
            prompt_parts.append(genai.protos.Part(text="Product Schema Data: Not available."))

        prompt_parts.append(genai.protos.Part(text="\n--- Your Answer ---"))
        prompt_parts.append(genai.protos.Part(text="Given the policy ID and the requested coverage element, answer directly if the policy is covered by the specified product based on the provided data. If information is missing or the product ID could not be extracted, state that."))

        print("SynthesisAgent: Generating final answer with LLM, referencing uploaded files...")
        try:
            time.sleep(3) # Added wait time here
            response = _generate_content_with_retry(self.model, prompt_parts) # Using retry helper
            return response.text.strip()
        except Exception as e:
            print(f"SynthesisAgent: Error generating final answer: {e}")
            return f"An error occurred while synthesizing the answer: {e}"