import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import logging

import requests
from dotenv import load_dotenv

# Try importing OpenAI, handle if not installed (though it should be)
try:
    from openai import OpenAI
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

# Call log: one line per LLM call (model, sizes, latency) -> data/logs/llm.log
_call_logger = logging.getLogger("llm_calls")
if not _call_logger.handlers:
    _log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _h = logging.FileHandler(os.path.join(_log_dir, "llm.log"), encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _call_logger.addHandler(_h)
    _call_logger.setLevel(logging.INFO)
    _call_logger.propagate = False


def _log_call(kind, provider, model, messages, system_prompt, output, t0):
    try:
        in_chars = len(system_prompt or "") + sum(len(m.get("content", "")) for m in messages)
        _call_logger.info(
            f"{kind} {provider}/{model} msgs={len(messages)} in~{in_chars // 4}tok "
            f"out~{len(output or '') // 4}tok {time.time() - t0:.1f}s")
    except Exception:
        pass


# Curated OpenRouter picks (price/value for narrative play, July 2026) — free text still allowed.
MAIN_MODELS = ["x-ai/grok-4.20", "x-ai/grok-4.5", "anthropic/claude-sonnet-5",
               "google/gemini-3.5-flash", "qwen/qwen3.7-max", "minimax/minimax-m3"]
UTIL_MODELS = ["google/gemini-3.1-flash-lite", "qwen/qwen3.7-plus", "minimax/minimax-m3",
               "tencent/hy3", "stepfun/step-3.7-flash"]
PROVIDERS = ["ollama", "claude_cli", "openrouter", "google"]


CLAUDE_MODELS = ["sonnet", "opus", "haiku"]
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "16384"))   # Ollama's default 4096 would cut off the Keeper's prompt
_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def ollama_base(base_url=None) -> str:
    base = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    return base[:-3].rstrip("/") if base.endswith("/v1") else base


class LLMError(Exception):
    """The model could not answer. The turn stops; nothing is written into the story."""


def check_llm(text):
    """chat() reports failures as a marked string; turn that back into an exception."""
    if text and text.startswith("[SYSTEM ERROR]"):
        raise LLMError(text)
    return text


class LLMClient:
    """
    Unified LLM Client for Coc_AI_Runner.
    Supports:
    1. Google Gemini (via google-genai-sdk)
    2. OpenRouter (via openai-sdk)
    3. Ollama (local GPU, no key; native API so the context size can be set)
    4. claude_cli (your Claude subscription through the logged-in `claude` command, no key)
    """
    def __init__(self, provider=None, model_name=None, api_key=None, base_url=None):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openrouter")).lower()
        self.model_name = model_name or os.getenv("LLM_MODEL", "x-ai/grok-4.20")
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
            self.base = ollama_base(self.base_url)

        elif self.provider == "claude_cli":
            self.exe = shutil.which("claude")
            if not self.exe:
                raise ValueError("The `claude` command was not found. Install Claude Code first.")

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def chat(self, messages, system_prompt=None, temperature=0.7, max_tokens=8192):
        """
        Multi-message chat completion.
        messages: [{"role": "user"|"assistant", "content": str}, ...]
        Extra keys (e.g. "name") are stripped before sending.
        """
        clean = [{"role": m["role"], "content": m["content"]} for m in messages]
        t0 = time.time()
        try:
            if self.provider in ("ollama", "claude_cli"):
                run = self._chat_ollama if self.provider == "ollama" else self._chat_claude
                out = run(clean, system_prompt, temperature, max_tokens)
                _log_call("chat", self.provider, self.model_name, messages, system_prompt, out, t0)
                return out
            if self.provider == "google":
                contents = [
                    types.Content(role="model" if m["role"] == "assistant" else "user",
                                  parts=[types.Part(text=m["content"])])
                    for m in clean
                ]
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                _log_call("chat", self.provider, self.model_name, messages, system_prompt, response.text, t0)
                return response.text
            else:
                if system_prompt:
                    clean.insert(0, {"role": "system", "content": system_prompt})
                completion = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=clean,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                out = completion.choices[0].message.content
                _log_call("chat", self.provider, self.model_name, messages, system_prompt, out, t0)
                return out
        except Exception as e:
            logger.error(f"LLM Chat Error: {e}")
            return f"[SYSTEM ERROR] The connection to beyond falters... (API Error: {str(e)})"

    def _chat_ollama(self, messages, system_prompt, temperature, max_tokens, json_mode=False):
        if "qwen3" in self.model_name.lower():   # these GGUFs ignore think:false
            system_prompt = (system_prompt or "") + " /no_think"
        msgs = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + messages
        body = {"model": self.model_name, "messages": msgs, "stream": False, "think": False,
                "options": {"temperature": temperature, "num_ctx": OLLAMA_NUM_CTX, "num_predict": max_tokens}}
        if json_mode:
            body["format"] = "json"
        r = requests.post(f"{self.base}/api/chat", json=body, timeout=900)
        if r.status_code != 200:
            raise RuntimeError(f"Ollama {r.status_code}: {r.text[:200]}")
        return _THINK_RE.sub("", r.json()["message"]["content"]).strip()

    def _chat_claude(self, messages, system_prompt, temperature=None, max_tokens=None):
        """One headless `claude -p` call. Uses the plan login; no tools, no project context."""
        prompt = "\n\n".join(f"[{'TABLE' if m['role'] == 'user' else 'YOU SAID EARLIER'}]\n{m['content']}"
                             for m in messages)
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}   # never API billing
        with tempfile.TemporaryDirectory() as tmp:
            sys_file = os.path.join(tmp, "system.txt")
            with open(sys_file, "w", encoding="utf-8") as f:
                f.write(system_prompt or "You are a helpful assistant.")
            r = subprocess.run(
                [self.exe, "-p", "--model", self.model_name, "--output-format", "json", "--tools", "",
                 "--strict-mcp-config", "--setting-sources", "", "--no-session-persistence",
                 "--disable-slash-commands", "--system-prompt-file", sys_file],
                input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=600, cwd=tmp, env=env)
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise RuntimeError((r.stderr or r.stdout or "no output from claude")[:300])
        if data.get("is_error"):
            raise RuntimeError(str(data.get("result"))[:300])
        return data.get("result") or ""

    def get_completion(self, prompt, system_prompt=None, temperature=0.7, max_tokens=8192, json_mode=False):
        """
        Unified method to get a text completion.
        """
        try:
            msgs = [{"role": "user", "content": prompt}]
            if self.provider == "ollama":
                return self._chat_ollama(msgs, system_prompt, temperature, max_tokens, json_mode)
            if self.provider == "claude_cli":
                out = self._chat_claude(msgs, system_prompt, temperature, max_tokens).strip()
                return re.sub(r"^```(?:json)?\s*|\s*```$", "", out)
            if self.provider == "google":
                return self._query_google(prompt, system_prompt, temperature, max_tokens, json_mode)
            elif self.provider == "openrouter":
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
            if self.provider in ("ollama", "claude_cli"):
                return not self.chat([{"role": "user", "content": "Ping"}], max_tokens=4).startswith("[SYSTEM ERROR]")
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
