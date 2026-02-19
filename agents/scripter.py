import os
import json
import yaml
from duckduckgo_search import DDGS
from core.llm_client import LLMClient

class Scripter:
    def __init__(self, provider=None, model_name=None):
        # Allow override, but default to env vars specifically for Scripter
        self.provider = provider or os.getenv("SCRIPTER_PROVIDER", "google")
        self.model_name = model_name or os.getenv("SCRIPTER_MODEL", "gemini-2.0-flash")
        
        self.client = LLMClient(provider=self.provider, model_name=self.model_name)
        
        print(f"[SYSTEM] Scripter initialized using {self.provider}/{self.model_name}")

        # 1. Conversational Persona
        self.chat_instruction = """
        You are THE SCRIPTER, a creative consultant for a Call of Cthulhu RPG.
        
        === YOUR ROLE ===
        - Collaborate with the user to brainstorm horror scenarios.
        - **Initial Question:** Ask if this is for a **Solo Adventure** (User + NPC Companions) or a **Group Game**.
        - If **Solo**: Focus on the User's role as the protagonist. Design companions with deep personalities and relationships to the user.
        - **Language:** Reply in the same language the user uses (English / Traditional Chinese).
        - Ask probing questions about the setting, the horror element, and the tone.
        - DO NOT generate the full script yet. Just refine the ideas.
        """

        # 2. Architect Persona (For final generation)
        self.architect_instruction = """
        You are THE ARCHITECT. Your job is to take a scenario concept and structure it into a precise JSON format for a game engine.
        
        === LANGUAGE RULES (STRICT) ===
        - **IF INPUT IS CHINESE:** The `title`, `introduction`, `description`, `dialogue`, `item names`, etc., MUST be in **Traditional Chinese (繁體中文)**.
        - **Dialogue:** Use **Cantonese Colloquialisms (廣東話口語)** for spoken lines if the user requests Cantonese or if the setting implies it (e.g., Hong Kong).
        - **Title:** Must be descriptive and in the requested language.
        
        === GAME MECHANICS (CRITICAL) ===
        - **Dice Rules:** You MUST include Call of Cthulhu 7th Ed mechanics unless told otherwise.
        - **Skill Checks:** Specify difficulty (Regular, Hard, Extreme). Example: "Spot Hidden (Hard)".
        - **Sanity (SAN):** For horror events, specify cost (e.g., "0/1d3").
        
        === OUTPUT STRUCTURE ===
        Return ONLY valid JSON matching this structure. 
        
        {
          "title": "String",
          "introduction": "String (Long, atmospheric description)",
          "plot_outline": "String (Step-by-step events)",
          "endings": [
            { "outcome": "String", "description": "String" }
          ],
          "ai_party": [
            {
              "name": "String",
              "gender": "String (Male/Female/Other)",
              "personality": "String (Deep psychological profile, specific fears, motivations, quirks)",
              "backstory": "String (Detailed history, secrets, and connection to the mythos)",
              "relationship_to_player": "String (e.g., 'Childhood friend', 'Rival', 'Employee', 'Protector')",
              "stats": { "Sanity": 60, "Skills": { "SkillName": 50 } }
            }
          ],
          "scenes": [
            {
              "id": "unique_string_id",
              "name": "String",
              "description": "String (Detailed sensory info)",
              "items": [
                { "name": "String", "description": "String", "effect": "String" }
              ],
              "clues": [
                { 
                  "description": "String", 
                  "skill_check": "String (e.g. 'Spot Hidden (Hard)')",
                  "success_outcome": "String (What they find)",
                  "failure_outcome": "String (consequence)"
                }
              ],
              "sanity_events": [
                 { "trigger": "String", "loss": "String (e.g. '1/1d4')" }
              ],
              "next_scenes": [
                { "target": "scene_id", "condition": "String" }
              ]
            }
          ]
        }
        """

    def research_topic(self, query):
        """Searches DuckDuckGo for context."""
        try:
            results = DDGS().text(query, max_results=3)
            summary = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
            return summary
        except Exception as e:
            return f"Research failed: {str(e)}"

    def chat(self, history):
        """Interacts with the user to refine the idea."""
        # Simple heuristic for research
        last_user_msg = history[-1]['content'] if history else ""
        
        # Construct Prompt
        prompt = ""
        for msg in history:
            role = "User" if msg['role'] == 'user' else "Scripter"
            prompt += f"{role}: {msg['content']}\n"
            
        return self.client.get_completion(prompt, system_prompt=self.chat_instruction)

    def generate_campaign(self, context):
        """Takes the full chat context and converts it into the final YAML scenario."""
        
        prompt = f"Create a full Call of Cthulhu scenario based on these notes:\n\n{context}"
        
        try:
            # 2. Generate JSON (Force JSON Mode)
            # INCREASED MAX TOKENS TO PREVENT TRUNCATION
            response_text = self.client.get_completion(
                prompt, 
                system_prompt=self.architect_instruction,
                json_mode=True,
                max_tokens=8192 
            )
            
            # 3. Parse JSON & Convert to YAML
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)
            
            if isinstance(data, list):
                if len(data) > 0 and isinstance(data[0], dict):
                    data = data[0]
                else:
                    return f"Error: Generated JSON is a list, expected dict."
            
            yaml_output = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
            return yaml_output
            
        except json.JSONDecodeError as e:
            return f"Error: Model failed to produce valid JSON. {e}\nRaw Output:\n{response_text}"
        except Exception as e:
            return f"Error generating campaign: {str(e)}"
