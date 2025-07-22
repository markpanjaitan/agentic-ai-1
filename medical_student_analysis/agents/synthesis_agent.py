# synthesis_agent.py

import google.generativeai as genai
import json

class SynthesisAgent:
    def __init__(self, gemini_model_name="gemini-1.5-flash"):
        self.model = genai.GenerativeModel(gemini_model_name)

    def synthesize_answer(self, user_question, db_results, doc_content=None):
        """
        Synthesizes a human-friendly answer based on query results and document content.
        """
        print("SynthesisAgent: Synthesizing final answer...")
        
        prompt_parts = [
            {"role": "user", "parts": [
                f"Original User Question: \"{user_question}\"\n\n"
            ]}
        ]

        if db_results is not None:
            # Convert db_results to a string representation if it's not already
            # This handles cases where db_results might be a list of dicts, etc.
            db_results_str = json.dumps(db_results, indent=2) if isinstance(db_results, (list, dict)) else str(db_results)
            # Clarified label
            prompt_parts[0]["parts"].append(f"Database Query Results (identifying the student):\n{db_results_str}\n\n") 
        else:
            # Clarified label
            prompt_parts[0]["parts"].append("Database Query Results: No relevant student identification data found or query failed.\n\n")

        if doc_content:
            # Clarified label
            prompt_parts[0]["parts"].append(f"Relevant Document Content (medical history details):\n{doc_content}\n\n") 
        else:
            prompt_parts[0]["parts"].append("Relevant Document Content: No relevant document found or content extraction failed.\n\n")

        # --- UPDATED PROMPT INSTRUCTIONS ---
        prompt_parts[0]["parts"].append(
            "Based on the 'Original User Question', use the 'Database Query Results' to identify the student by name. "
            "Then, use this identified student's name to find their corresponding medical history in the 'Relevant Document Content'. "
            "Finally, extract the *latest* or most relevant medical record for that specific student. "
            "Provide a concise and clear answer to the original user question. "
            "If the student cannot be identified or their medical record is not found in the documents, clearly state that. "
            "Prioritize direct answers if available. "
            "Output only the answer, no extra text or comments."
        )
        # --- END UPDATED PROMPT INSTRUCTIONS ---

        # --- DEBUG PRINT FOR PROMPT_PARTS ---
        print("\n--- SynthesisAgent: PROMPT PARTS (DEBUG) ---")
        # Use json.dumps for a more readable output of the list of dicts
        print(json.dumps(prompt_parts, indent=2))
        print("--- END PROMPT PARTS (DEBUG) ---\n")
        # --- END DEBUG PRINT ---         

        try:
            response = self.model.generate_content(
                prompt_parts,
                generation_config={"max_output_tokens": 500}
            )
            return response.text.strip()
        except Exception as e:
            print(f"SynthesisAgent: Failed to generate summary: {e}")
            return "An error occurred while trying to synthesize the answer."