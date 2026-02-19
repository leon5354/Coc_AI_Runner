import json
import os
from typing import Dict, List, Any

class MemorySystem:
    def __init__(self, save_dir: str = "data/saves"):
        self.save_dir = save_dir
        self.memory_file = None
        self.data = {
            "global_context": {
                "summary": "The investigation begins.",
                "key_clues": [],
                "location_state": "Unknown location.",
                "turn_count": 0
            },
            "character_memories": {},
            "short_term_buffer": []  # <--- NEW: Stores recent conversation for summarization
        }
        self.summary_threshold = 5  # Summarize every 5 turns (adjust as needed)

    def load_memory(self, campaign_name: str):
        """Loads the memory file associated with a campaign/save."""
        self.memory_file = os.path.join(self.save_dir, f"{campaign_name}_memory.json")
        if os.path.exists(self.memory_file):
            with open(self.memory_file, 'r') as f:
                loaded_data = json.load(f)
                # Merge loaded data with defaults to ensure new fields exist
                self.data.update(loaded_data)
                if "short_term_buffer" not in self.data:
                    self.data["short_term_buffer"] = []
        else:
            self.save_memory()

    def save_memory(self):
        """Persists the current memory state to JSON."""
        if self.memory_file:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, 'w') as f:
                json.dump(self.data, f, indent=2)

    def add_to_buffer(self, role: str, content: str):
        """Adds a message to the short-term buffer."""
        self.data["short_term_buffer"].append(f"{role}: {content}")
        self.save_memory()

    def should_summarize(self) -> bool:
        """Checks if the buffer has reached the threshold."""
        return len(self.data["short_term_buffer"]) >= self.summary_threshold

    def get_buffer_content(self) -> str:
        """Returns the content of the buffer as a string."""
        return "\n".join(self.data["short_term_buffer"])

    def clear_buffer(self):
        """Clears the short-term buffer after summarization."""
        self.data["short_term_buffer"] = []
        self.save_memory()

    def update_global_context(self, summary: str = None, new_clues: List[str] = None, location: str = None):
        """Updates the shared narrative context."""
        if summary:
            # Append new summary to existing summary, keeping it concise
            current_summary = self.data["global_context"].get("summary", "")
            # Simple concatenation for now, ideal would be full rewrite
            if current_summary == "The investigation begins.":
                self.data["global_context"]["summary"] = summary
            else:
                self.data["global_context"]["summary"] = f"{current_summary}\n\n[UPDATE]: {summary}"
                
        if new_clues:
            existing = set(self.data["global_context"].get("key_clues", []))
            for clue in new_clues:
                if clue not in existing:
                    self.data["global_context"].setdefault("key_clues", []).append(clue)
                    
        if location:
            self.data["global_context"]["location_state"] = location
        
        self.save_memory()

    def get_global_context_str(self) -> str:
        """Returns a formatted string of the global context for the LLM."""
        ctx = self.data["global_context"]
        summary = ctx.get("summary", "No summary yet.")
        location = ctx.get("location_state", "Unknown")
        clues = ", ".join(ctx.get("key_clues", []))
        
        return (
            f"--- CURRENT SITUATION (GLOBAL MEMORY) ---\n"
            f"SUMMARY: {summary}\n"
            f"LOCATION: {location}\n"
            f"KNOWN CLUES: {clues}\n"
            f"-----------------------------------------"
        )
