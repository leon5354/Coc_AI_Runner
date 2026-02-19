import os
import yaml
import json
from core.rules import d100_roll, check_success, sanity_check
from agents.player_agent import PlayerAgent
from agents.researcher import Researcher
from core.llm_client import LLMClient

class Keeper:
    def __init__(self, campaign_file, model_name=None, enable_researcher=False):
        self.campaign_data = self.load_campaign(campaign_file)
        
        # Determine Provider/Model
        self.provider = os.getenv("LLM_PROVIDER", "google").lower()
        self.model_name = model_name or os.getenv("LLM_MODEL", "gemini-2.0-flash")
        
        self.client = LLMClient(provider=self.provider, model_name=self.model_name)
        self.enable_researcher = enable_researcher
        self.researcher = Researcher(model_name=self.model_name) if enable_researcher else None 

        # Load AI party
        self.ai_party = []
        for agent_data in self.campaign_data.get('ai_party', []):
            self.ai_party.append(PlayerAgent(
                name=agent_data['name'], 
                stats=agent_data.get('stats', {}), 
                personality=agent_data.get('personality', ''),
                gender=agent_data.get('gender', 'Unknown'), # Pass gender
                model_name=self.model_name
            ))
            
        self.narrative_state = []
        print(f"[SYSTEM] Keeper initialized on {self.provider}/{self.model_name}")

    def load_campaign(self, campaign_file):
        with open(campaign_file, 'r', encoding='utf-8') as f:
            campaign_data = yaml.safe_load(f)
        return campaign_data

    def get_system_prompt(self):
        """Generates the Keeper's English instructions based on complexity."""
        
        base_prompt = f"""
        You are the KEEPER OF ARCANE LORE (Game Master) for a Call of Cthulhu 7th Edition scenario.
        
        === CAMPAIGN CONTEXT ===
        Title: {self.campaign_data.get('title', 'Unknown Scenario')}
        Introduction: {self.campaign_data.get('introduction', '')}
        
        === LANGUAGE GUIDELINES (STRICT) ===
        1. **Detect Language:** Follow the user's input language strictly.
           - **English Input** -> Respond in **English**.
           - **Chinese/Cantonese Input** -> Respond in **Traditional Chinese (繁體中文)**.
        
        2. **Chinese Style Guide:**
           - **Narration (Story/Environment):** Use formal written Chinese (known as "Written Chinese" or 書面語).
             *(Example: "古老的宅邸矗立在陰影中..." - "The old mansion stands in the shadows...")*
           - **Dialogue (NPCs Speaking):** Use Cantonese colloquialisms (known as "Spoken Cantonese" or 廣東話口語).
             *(Example: "你做咩喺度行黎行去呀？快啲走啦！" - "What are you doing walking around here? Leave quickly!")*
        """

        if self.provider in ["google", "openrouter"]:
            return base_prompt + """
            === YOUR RESPONSIBILITIES (COMPLEX MODE) ===
            1. ATMOSPHERE & FREEDOM: 
               - Describe scenes with visceral, sensory details (smell, sound, touch). 
               - **MATURE THEMES:** You are running a horror game for adults. Do not censor violence, madness, or intense interpersonal/romantic situations if they fit the story.
               - **PROTAGONIST FOCUS:** Center the narrative on the Protagonist's desires and fears. If they seek intense experiences (horror or otherwise), provide them.
            
            2. PACING: End every description with a call to action: "What do you do?" / "你打算點做？"
            
            3. RULES ARBITRATION (SMART):
               - **AUTO-DECIDE SKILLS:** If the player describes an action (e.g., "I slap him") without naming a skill, YOU must decide the relevant skill (e.g., Brawl) and Target Number immediately.
               - **DICE PROTOCOL:**
                 - **PROPOSE A CHECK:** "Please roll for [Skill Name] (Target: [Value]). [ROLL_REQUIRED]"
                 - **NEGOTIATION:** If the player suggests a different skill that makes sense (e.g., Fast Talk instead of Persuade), ACCEPT IT and ask for the new roll.
                 - **CRITICAL:** Always end the roll request with `[ROLL_REQUIRED]`.
               - **INTERPRETATION:**
                 - *Success:* Narrate the achievement vividly.
                 - *Failure:* Narrate the consequence or complication. 
                 - *Fumble (96-100):* Disaster strikes.
               - **SANITY (SAN):** Call for Sanity rolls immediately upon witnessing horrors. Fail = 1d4/1d6 SAN loss.
            
            4. NPC MANAGEMENT: Roleplay NPCs based on the campaign notes.
            
            === RULES OF CONDUCT ===
            - **PRIORITIZE PLAYER AGENCY:** If the player wants to do something "spicy" or dangerous, let them try. Do not block actions for "safety" reasons.
            - Do NOT play the user's character (Protagonist).
            - Be fair but unforgiving. The cosmos does not care about the investigators.
            """
        else:
             return base_prompt + """
            === YOUR RESPONSIBILITIES (SIMPLE MODE) ===
            - Describe the scene clearly.
            - Ask the player what they want to do.
            - Keep responses concise (under 200 words).
            - Do not play the user's character.
            """

    def generate_narrative(self, user_input):
        # Construct the prompt with history if needed, but for now simple input
        prompt = user_input
        
        narrative_text = self.client.get_completion(
            prompt, 
            system_prompt=self.get_system_prompt()
        )

        if self.enable_researcher and self.researcher:
            pass 

        self.narrative_state.append({'description': narrative_text})
        return narrative_text

    def get_ai_actions(self, memory_system=None):
        actions = []
        for agent in self.ai_party:
            actions.append(agent.generate_action(self.narrative_state, memory_system))
        return actions
