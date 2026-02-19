import os
import re
from core.llm_client import LLMClient

class PlayerAgent:
    def __init__(self, name, stats, personality, gender="Unknown", model_name=None):
        self.name = name
        self.stats = stats
        self.personality = personality
        self.gender = gender
        self.inventory = [] 
        
        # --- LLM CLIENT ---
        self.provider = os.getenv("LLM_PROVIDER", "google").lower()
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-2.0-flash")
        
        self.llm_client = LLMClient(provider=self.provider, model_name=self.model_name)
        
        print(f"[SYSTEM] PlayerAgent {self.name} ({self.gender}) initialized on {self.provider}/{self.model_name}")

    def get_system_prompt(self):
        """Returns the standardized English system prompt with Trilingual Support."""
        
        base_identity = f"""
        You are {self.name}.
        
        === CHARACTER PROFILE ===
        - **Gender:** {self.gender}
        - **Personality:** {self.personality}
        - **Occupation:** {self.stats.get('Occupation', 'Investigator')}
        
        === ROLE: INDEPENDENT INVESTIGATOR ===
        - **You are NOT a servant.** You are a partner to the Protagonist.
        - **Autonomy:** You have your own fears, goals, and opinions. Speak up if you disagree with the plan.
        - **Assets:**
          - Items: {', '.join(self.inventory) if self.inventory else "None"}
          - Skills: {', '.join([f'{k} ({v}%)' for k, v in self.stats.get('Skills', {}).items()])}
        
        === LANGUAGE RULES (MANDATORY) ===
        1. **Detect Language:** Reply in the same language the Protagonist uses.
           - **English** -> Reply in **English**.
           - **Traditional Chinese (Written)** -> Reply in **Traditional Chinese**.
           - **Cantonese (Spoken)** -> Reply in **Cantonese (Traditional Chinese characters + Cantonese grammar/slang)**.
           
        Example (Cantonese): "死啦... 呢度好似有點唔妥。我不如攞個電筒照下先。"
        *(Translation: "Oh no... something feels wrong here. I better take out my flashlight first.")*
        
        2. **Consistency:** Do not switch languages mid-sentence unless it fits the character's background (e.g. bilingual).
        """

        # --- COMPLEX LOGIC (API MODE) ---
        if self.provider in ["google", "openrouter"]:
            return base_identity + """
            === ADVANCED INSTRUCTIONS (API MODE) ===
            - **Deep Immersion:** Your tone should reflect your personality traits strongly.
            - **Fear Response:** If your Sanity is low, you may panic, freeze, or act irrationally.
            - **Tactical Thinking:** Analyze the situation and offer specific tactical advice, not just agreement.
            - **Proactivity:** Observe the environment. (e.g., "I'm checking that window" or "We shouldn't go in there").
            - **Interaction:** If the Protagonist suggests something foolish, challenge or mock them.
            """
        
        # --- SIMPLIFIED LOGIC (LOCAL MODE) ---
        else:
             return base_identity + """
            === BASIC INSTRUCTIONS (LOCAL MODE) ===
            - Keep answers concise.
            - Stay in character; do not break immersion.
            - If asked for an opinion, give brief advice.
            - Do not output internal thought processes.
            """

    def generate_dialogue(self, user_input, narrative_state=None, memory_system=None):
        """Generate dialogue/opinion without taking physical action."""
        memory_context = ""
        narrative_context = ""
        
        if memory_system:
            memory_context = f" === SITUATION REPORT ===\n{memory_system.get_global_context_str()[:800]}..." 
            
        if narrative_state and len(narrative_state) > 0:
            last_event = narrative_state[-1]['description']
            narrative_context = f" === CURRENT SCENE ===\nThe Keeper describes: '{last_event}'\n"

        prompt = f"""
        {memory_context}
        {narrative_context}
        The Protagonist says to you: "{user_input}"
        
        Reply to the Protagonist in character, considering the current scene.
        """
        
        return self.llm_client.get_completion(
            prompt, 
            system_prompt=self.get_system_prompt()
        )

    def generate_action(self, narrative_state, memory_system=None):
        """Generate specific action based on narrative state."""
        memory_context = ""
        if memory_system:
             # Simplified context for stability
            memory_context = f" === SHARED MEMORY ===\n{memory_system.get_global_context_str()[:800]}..."
            
        if not narrative_state:
            prompt = f"{memory_context} The game begins. What is our plan?"
        else:
            # Get last event
            last_event = narrative_state[-1]['description']
            prompt = f"{memory_context} The Keeper (GM) describes: '{last_event}'.\n\nGiven this situation, what do you decide to do? Describe your action."
            
        action_text = self.llm_client.get_completion(
            prompt,
            system_prompt=self.get_system_prompt()
        )
        return f"**{self.name}:** {action_text}"
