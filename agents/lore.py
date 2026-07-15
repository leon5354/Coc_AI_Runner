"""Fetch real setting canon from official wikis at campaign-generation time.

The canon is baked into the campaign YAML (a `canon:` block) so PLAY needs no live lookups.
Fandom/Lexicanum run MediaWiki, whose api.php gives search + plain-text extracts over HTTP.
Everything degrades gracefully to "" on any network/parse failure — lore is a bonus, not a gate.
"""
import re

import requests

# setting key -> (label, MediaWiki api.php base). Add more freely.
SETTING_WIKIS = {
    "generic":  ("Generic / homebrew", None),
    "cthulhu":  ("Cthulhu Mythos", "https://lovecraft.fandom.com/api.php"),
    "forgotten_realms": ("D&D — Forgotten Realms", "https://forgottenrealms.fandom.com/api.php"),
    "warhammer_fantasy": ("Warhammer Fantasy", "https://warhammerfantasy.fandom.com/api.php"),
    "warhammer_40k": ("Warhammer 40,000", "https://warhammer40k.fandom.com/api.php"),
}

# sensible default wiki per rule system (used when the user doesn't pick one)
DEFAULT_SETTING = {"coc7e": "cthulhu", "dnd5e": "forgotten_realms",
                   "wfrp": "warhammer_fantasy", "basic_d100": "generic"}

_HEADERS = {"User-Agent": "CoC-AI-Runner/1.0 (hobby TTRPG tool)"}
_TIMEOUT = 12


def _search_titles(api: str, query: str, limit: int) -> list:
    r = requests.get(api, params={"action": "query", "list": "search", "srsearch": query,
                                  "srlimit": limit, "format": "json"},
                     headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    return [hit["title"] for hit in r.json().get("query", {}).get("search", [])]


def _strip_html(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|table|sup|figure)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)                 # drop remaining tags
    html = re.sub(r"&#?\w+;", " ", html)                     # entities
    return re.sub(r"[ \t]*\n[ \t]*", "\n", re.sub(r"[ \t]{2,}", " ", html)).strip()


def _extract(api: str, title: str) -> str:
    # Preferred: TextExtracts (plain-text intro). Many Fandom wikis lack it, so fall back
    # to action=parse of the lead section (rendered HTML) and strip tags.
    r = requests.get(api, params={"action": "query", "prop": "extracts", "exintro": 1,
                                  "explaintext": 1, "redirects": 1, "titles": title,
                                  "format": "json"},
                     headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    for p in r.json().get("query", {}).get("pages", {}).values():
        if p.get("extract"):
            return re.sub(r"\n{2,}", "\n", p["extract"]).strip()

    r = requests.get(api, params={"action": "parse", "page": title, "prop": "text",
                                  "section": 0, "redirects": 1, "format": "json"},
                     headers=_HEADERS, timeout=_TIMEOUT)
    r.raise_for_status()
    html = r.json().get("parse", {}).get("text", {}).get("*", "")
    return _strip_html(html) if html else ""


def fetch_pages(setting: str, terms: list, max_pages: int = 4) -> list:
    """Return [(title, extract)] from the setting's wiki for the given search terms. [] on any failure."""
    api = SETTING_WIKIS.get(setting, (None, None))[1]
    if not api or not terms:
        return []
    out, seen = [], set()
    try:
        for term in terms:
            for title in _search_titles(api, term, 2):
                if title in seen:
                    continue
                seen.add(title)
                text = _extract(api, title)
                if text:
                    out.append((title, text[:1500]))
                if len(out) >= max_pages:
                    return out
    except (requests.RequestException, ValueError):
        return out   # partial results are fine; canon is optional
    return out


CANON_PROMPT = """You are a loremaster. From the wiki extracts below, write a tight CANON BRIEF
(<=300 words) an AI game master can rely on to keep a scenario faithful to this setting:
key factions, places, tone, names, and rules-of-the-world that matter. Plain prose, no citations,
no markdown headers. If the extracts are thin, write only what they support."""


def fetch_canon(setting: str, concept: str, llm, max_pages: int = 4) -> str:
    """Search the setting wiki using terms from the concept, then compress to a canon brief.
    Returns "" if the setting has no wiki or nothing usable was found."""
    if setting in (None, "generic") or setting not in SETTING_WIKIS:
        return ""
    terms = _concept_terms(concept)
    pages = fetch_pages(setting, terms, max_pages)
    if not pages:
        return ""
    corpus = "\n\n".join(f"== {t} ==\n{x}" for t, x in pages)
    brief = llm.chat([{"role": "user", "content": f"SETTING: {SETTING_WIKIS[setting][0]}\n\n"
                                                   f"WIKI EXTRACTS:\n{corpus}"}],
                     system_prompt=CANON_PROMPT, temperature=0.3, max_tokens=500)
    if not brief or brief.startswith("[SYSTEM ERROR]"):
        return ""
    src = ", ".join(t for t, _ in pages)
    return f"{brief.strip()}\n\n(Grounded in: {src})"


_STOP = {"the", "a", "an", "of", "and", "in", "on", "with", "for", "to", "is", "are", "at",
         "player", "players", "scenario", "campaign", "want", "like", "story", "game"}


def _concept_terms(concept: str, k: int = 4) -> list:
    """Pick the most distinctive words/phrases from the concept to search the wiki with."""
    # keep multi-word Proper Noun phrases first (e.g. "Miskatonic University")
    phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", concept)
    words = [w for w in re.findall(r"[A-Za-z]{4,}", concept) if w.lower() not in _STOP]
    seen, terms = set(), []
    for t in phrases + words:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            terms.append(t)
        if len(terms) >= k:
            break
    return terms


if __name__ == "__main__":
    assert _concept_terms("A haunting at Miskatonic University with a cursed tome") \
        [:1] == ["Miskatonic University"]
    assert "generic" in SETTING_WIKIS and SETTING_WIKIS["generic"][1] is None

    class _M:
        def chat(self, *a, **k): return "A brief."
    assert fetch_canon("generic", "anything", _M()) == ""      # no wiki -> no canon
    print("lore: offline checks passed")
