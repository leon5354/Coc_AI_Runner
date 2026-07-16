"""The Archivist: produces diegetic lore handouts (newspaper clippings, journal pages)."""

SYSTEM_PROMPT = """You are the Archivist of a vast occult library, assisting a tabletop horror game.
Given a research query and the current game context, produce ONE short diegetic handout the
investigators could plausibly find: a newspaper clipping, journal fragment, library excerpt,
or letter. 100-180 words, with a plausible dateline/source. Ground it in the campaign context
provided — enrich the mystery, never contradict established facts, never spoil undiscovered
secrets outright (hint at most)."""


class Researcher:
    def __init__(self, llm):
        self.llm = llm

    def consult(self, query: str, state, campaign, use_web: bool = False) -> str:
        web_notes = ""
        if use_web:
            try:
                from duckduckgo_search import DDGS
                hits = DDGS().text(query, max_results=3)
                web_notes = "\n".join(f"- {h['title']}: {h['body']}" for h in hits)
            except Exception:
                web_notes = ""

        discovered = "\n".join(
            f"- {cid}: {campaign.clue(cid).get('reveals', '')}" for cid in state.discovered_clues
            if campaign.clue(cid)
        ) or "(nothing yet)"
        scene = campaign.scene(state.scene_id) or {}
        prompt = f"""CAMPAIGN: {campaign.title}
CURRENT SCENE: {scene.get('name', '?')}
CLUES THE PARTY HAS DISCOVERED:
{discovered}
{f'REAL-WORLD SEARCH NOTES (for flavor only):{chr(10)}{web_notes}' if web_notes else ''}
RESEARCH QUERY: {query}"""

        from core.keeper import language_block
        system_prompt = SYSTEM_PROMPT + "\n\n" + language_block(state.language)
        return self.llm.chat([{"role": "user", "content": prompt}],
                             system_prompt=system_prompt, temperature=0.8, max_tokens=400) or ""
