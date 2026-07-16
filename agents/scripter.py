"""Scenario architect: brainstorm via chat, then generate a canonical schema-v2 campaign."""
import json
import os

import yaml

import rules
from core import campaign as campaign_mod
from core.llm_client import LLMClient

CHAT_INSTRUCTION = """You are THE SCRIPTER, a creative consultant for tabletop horror scenarios.

=== YOUR ROLE ===
- Collaborate with the user to brainstorm a scenario.
- Initial question: is this a Solo Adventure (user + AI companions) or a Group Game?
- If Solo: design companions with deep personalities and relationships to the user.
- Ask probing questions about the setting, the horror element, and the tone.
- Reply in the same language the user uses (English / Traditional Chinese).
- DO NOT generate the full script yet. Just refine the ideas."""

ARCHITECT_INSTRUCTION_TEMPLATE = """You are THE ARCHITECT. Convert a scenario concept into precise JSON for a game engine.

=== LANGUAGE RULES (STRICT) ===
- IF INPUT IS CHINESE: title, introduction, descriptions, dialogue, item names MUST be Traditional Chinese (繁體中文).
- Dialogue: use Cantonese colloquialisms (廣東話口語) when the user requests Cantonese or the setting implies it.

=== MECHANICS ===
- rule_system is "{rule_system}". Allowed clue difficulties: {difficulties}.
- {stress_rule}
- Every scene, clue, and stress_event needs a unique snake_case id. Every exit "to" must name an existing scene id.
- 4-7 scenes. Each scene: 1-3 clues, 0-2 stress_events, 1-3 exits (final scenes may have fewer).

=== WRITE FOR AN AI GAME MASTER, NOT A HUMAN ===
The keeper running this is an LLM. Unlike a human GM it cannot improvise from vague notes, so be
explicit where a human module would rely on experience:
- plot_outline: the FULL truth in 150-300 words — what really happened, who/what the antagonist is,
  what it wants, how it reacts if the players do nothing, and how each ending can be reached.
- Each scene's keeper_notes: pacing advice, what the antagonist is doing meanwhile, what happens if
  players stall or go loud, which clue is critical, improv hooks for likely player ideas.
- npcs: every named character with a distinct voice cue the AI can imitate consistently.
- escalation: 3-5 ordered beats the keeper advances when the story needs pressure.
- protagonist: the PLAYER's own character — name, role,背景, and a starting kit that FITS this
  setting and rule system (a Warhammer inquisitor carries a bolt pistol and rosette, not a
  smartphone; a 1920s investigator carries a notebook). Never leave the player as a generic
  "Player". Their skills and inventory must match {rule_system} and the fiction.
- ALL stats (protagonist and ai_party) must use {rule_system} conventions: {stat_note}

=== OUTPUT STRUCTURE ===
Return ONLY valid JSON matching exactly:
{{
  "schema_version": 2,
  "rule_system": "{rule_system}",
  "title": "String",
  "introduction": "String (long, atmospheric, read to players)",
  "plot_outline": "String (keeper-eyes-only FULL truth: antagonist, its goal, its timetable, paths to each ending)",
  "tone": "String (e.g. slow-burn dread, pulpy action-horror)",
  "protagonist": {{
    "name": "String (the player character's name — NOT 'Player')", "gender": "String",
    "occupation": "String (their role in this setting)",
    "personality": "String (temperament, quirks)",
    "backstory": "String (who they are, why they're here, a hook tying them to the plot)",
    "stats": {{"HP": 12, "Stress": 50, "Skills": {{"SkillName": 50}}}},
    "inventory": ["String (starting gear that fits the setting)"]
  }},
  "npcs": [{{"name": "String", "role": "String", "motivation": "String",
             "secret": "String", "voice": "String (speech pattern the AI keeper imitates)"}}],
  "escalation": ["String (beat 1: what the antagonist does first)", "String (beat 2...)"],
  "endings": [{{"outcome": "snake_case_id", "description": "String"}}],
  "ai_party": [
    {{
      "name": "String", "gender": "String",
      "personality": "String (psychological profile, fears, motivations, quirks)",
      "backstory": "String (history, secrets, mythos connection)",
      "relationship_to_player": "String",
      "stats": {{"HP": 10, "Stress": 60, "Skills": {{"SkillName": 50}}}}
    }}
  ],
  "scenes": [
    {{
      "id": "snake_case_id",
      "name": "String",
      "description": "String (detailed sensory info for the keeper)",
      "keeper_notes": "String (private GM advice: pacing, antagonist activity, stall/loud contingencies, critical clue)",
      "mood": "daylight|dusk|night|unearthly (visual/audio atmosphere of the scene; escalate with the horror)",
      "clues": [
        {{"id": "snake_case_id", "description": "String (what draws attention)",
          "skill": "String (skill name)", "difficulty": "regular",
          "reveals": "String (what is learned when discovered)"}}
      ],
      "items": [{{"name": "String", "description": "String", "effect": "String"}}],
      "stress_events": [{{"id": "snake_case_id", "trigger": "String", "loss": "0/1d4"}}],
      "exits": [{{"to": "scene_id", "condition": "String"}}]
    }}
  ]
}}"""


class Scripter:
    def __init__(self, provider=None, model_name=None):
        self.provider = provider or os.getenv("SCRIPTER_PROVIDER") or os.getenv("LLM_PROVIDER", "openrouter")
        self.model_name = model_name or os.getenv("SCRIPTER_MODEL") or os.getenv("LLM_MODEL", "x-ai/grok-4.20")
        self.client = LLMClient(provider=self.provider, model_name=self.model_name)

    def chat(self, history):
        """Brainstorm with the user. history: [{role, content}]"""
        msgs = [{"role": "assistant" if m["role"] == "assistant" else "user", "content": m["content"]}
                for m in history]
        return self.client.chat(msgs, system_prompt=CHAT_INSTRUCTION)

    def generate_campaign(self, context: str, rule_system: str = "coc7e", setting: str = "generic"):
        """Generate + validate a campaign. Returns (yaml_text, None) or (None, error_string).
        If `setting` names a real-world wiki, fetch canon and ground the plot in it (baked into
        the YAML `canon:` block so play needs no lookups). One repair round-trip on validation."""
        system = rules.get_system(rule_system)
        stress_rule = ('Stress/sanity loss expressions look like "0/1d4", "1/1d6", "1d4/1d8" '
                       '(success loss / failure loss).' if system.has_stress else
                       'This rule system has NO sanity/stress mechanic: every "stress_events" list MUST be [].')
        stat_note = ("skill values are d20 MODIFIERS like +2..+6 (ability + proficiency), NOT "
                     "percentages; give sensible HP (10-30) and set Stress to 0."
                     if rule_system == "dnd5e" else
                     "skill values are 0-100 percentages (a trained skill is ~40-70); HP is small "
                     "(8-15). Example skills for this system: "
                     + ", ".join(list(system.character_sheet_defaults().get("Skills", {}))[:6]) + ".")
        instruction = ARCHITECT_INSTRUCTION_TEMPLATE.format(
            rule_system=rule_system, difficulties=system.difficulty_levels,
            stress_rule=stress_rule, stat_note=stat_note)

        canon = ""
        if setting and setting != "generic":
            from agents import lore
            canon = lore.fetch_canon(setting, context, self.client)

        prompt = f"Create a full scenario based on these notes:\n\n{context}"
        if canon:
            prompt += (f"\n\n=== ESTABLISHED CANON for this setting — stay faithful to it; use these "
                       f"names, places, and tone ===\n{canon}")

        raw = self.client.get_completion(prompt, system_prompt=instruction,
                                         json_mode=True, max_tokens=8192)
        data, err = self._parse(raw)
        problems = campaign_mod.validate(data) if err is None else [err]

        if problems:  # one repair round-trip
            repair = ("Your previous output failed validation:\n- " + "\n- ".join(problems)
                      + f"\n\nPrevious output:\n{raw}\n\nReturn the corrected, complete JSON only.")
            raw = self.client.get_completion(repair, system_prompt=instruction,
                                             json_mode=True, max_tokens=8192)
            data, err = self._parse(raw)
            problems = campaign_mod.validate(data) if err is None else [err]

        if problems:
            return None, "Generation failed validation:\n- " + "\n- ".join(problems)
        if setting and setting != "generic":
            data["setting"] = setting
        if canon:
            data["canon"] = canon
        return yaml.dump(data, allow_unicode=True, sort_keys=False, width=1000), None

    @staticmethod
    def _parse(raw):
        if not raw:
            return None, "Empty model response"
        clean = raw.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON: {e}"
        if isinstance(data, list):
            data = data[0] if data and isinstance(data[0], dict) else None
        if not isinstance(data, dict):
            return None, "Expected a JSON object"
        data.setdefault("schema_version", 2)
        return data, None
