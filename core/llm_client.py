import os
import time
import json
import logging
from dotenv import load_dotenv

# Try importing OpenAI, handle if not installed (though it should be)
try:
    from openai import OpenAI, APIError, APIConnectionError, RateLimitError
except ImportError:
    OpenAI = None

# Try importing Google GenAI
try:
    import google.genai as genai
    from google.genai import types
except ImportError:
    genai = None

load_dotenv()

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMClient:
    """
    Unified LLM Client for Coc_AI_Runner.
    Supports:
    1. Google Gemini (via google-genai-sdk)
    2. OpenRouter (via openai-sdk)
    3. Ollama (via openai-sdk compatible endpoint)
    """
    def __init__(self, provider=None, model_name=None, api_key=None, base_url=None):
        self.provider = provider or os.getenv("LLM_PROVIDER", "google").lower()
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-2.0-flash")
        self.api_key = api_key
        self.base_url = base_url
        self.client = None

        self._initialize_client()

    def _initialize_client(self):
        """Initializes the specific SDK client based on provider."""
        logger.info(f"Initializing LLMClient: Provider={self.provider}, Model={self.model_name}")

        if self.provider == "google":
            if not genai:
                raise ImportError("google.genai module not found. Install with `pip install google-genai`")
            
            key = self.api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not key:
                raise ValueError("Missing GOOGLE_API_KEY for Google provider.")
            
            self.client = genai.Client(api_key=key)

        elif self.provider == "openrouter":
            if not OpenAI:
                raise ImportError("openai module not found. Install with `pip install openai`")
            
            key = self.api_key or os.getenv("OPENROUTER_API_KEY")
            if not key:
                raise ValueError("Missing OPENROUTER_API_KEY for OpenRouter provider.")
            
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
            )

        elif self.provider == "ollama":
            if not OpenAI:
                raise ImportError("openai module not found. Install with `pip install openai`")
            
            # Ollama local endpoint
            base = self.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
            self.client = OpenAI(
                base_url=base,
                api_key="ollama", # Key is required but ignored by Ollama
            )

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def get_completion(self, prompt, system_prompt=None, temperature=0.7, max_tokens=8192, json_mode=False):
        """
        Unified method to get a text completion.
        """
        try:
            if self.provider == "google":
                return self._query_google(prompt, system_prompt, temperature, max_tokens, json_mode)
            elif self.provider in ["openrouter", "ollama"]:
                return self._query_openai_compatible(prompt, system_prompt, temperature, max_tokens, json_mode)
        except Exception as e:
            logger.error(f"LLM Generation Error: {e}")
            return f"[SYSTEM ERROR] The investigator's mind is clouded... (API Error: {str(e)})"

    def _query_google(self, prompt, system_prompt, temperature, max_tokens, json_mode):
        """Handles Google Gemini API calls."""
        config_args = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        if json_mode:
            config_args["response_mime_type"] = "application/json"

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(**config_args)
        )
        return response.text

    def _query_openai_compatible(self, prompt, system_prompt, temperature, max_tokens, json_mode):
        """Handles OpenRouter and Ollama calls via OpenAI SDK."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})

        response_format = {"type": "json_object"} if json_mode else None

        # Note: 'max_tokens' handling varies, OpenRouter/Ollama usually respect it.
        # Ollama sometimes needs 'num_predict' in raw mode, but v1 compat should handle max_tokens.
        
        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )
        
        return completion.choices[0].message.content

    def check_connection(self):
        """Simple ping to verify connectivity."""
        try:
            if self.provider == "google":
                self.client.models.generate_content(model=self.model_name, contents="Ping")
            else:
                self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": "Ping"}],
                    max_tokens=1
                )
            return True
        except Exception as e:
            logger.error(f"Connection Check Failed: {e}")
            return False
