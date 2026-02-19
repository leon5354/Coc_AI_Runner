import os
import re
from core.llm_client import LLMClient

class Researcher:
    def __init__(self, model_name=None):
        self.provider = os.getenv("LLM_PROVIDER", "google").lower()
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-2.0-flash")
        
        self.client = LLMClient(provider=self.provider, model_name=self.model_name)
        
        self.system_prompt = """
        You are a Miskatonic University Researcher.
        Your job is to provide historical context or occult knowledge when called upon.
        Keep it brief and relevant to the investigation.
        """

    def generate_multimedia(self, narrative_context):
        """Simulates finding a document or image description."""
        prompt = f"Based on this narrative, describe a relevant handout, letter, or visual clue found at the scene: {narrative_context[:500]}"
        return self.client.get_completion(prompt, system_prompt=self.system_prompt)
