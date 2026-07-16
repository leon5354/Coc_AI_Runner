"""The Keeper must not speak/act for AI companions in player mode (they're real players),
but MAY voice them as NPCs in solo or cinematic mode. Run: python test_authority.py"""
from core.keeper import character_authority_clause
from core.engine import new_game
from pathlib import Path

CAMP = Path("data/campaigns/the_haunting.yaml")
st = new_game(CAMP)          # protagonist (human) + Prof. Warren Vale (ai)
human, ai = st.characters[0].name, "Prof. Warren Vale"


def clause(style, party):
    st.companion_style, st.party_mode = style, party
    return character_authority_clause(st)


# player mode, companions act on their own turns -> AI is a protected player, not voiced by Keeper
c = clause("player", "keeper")
assert human in c and ai in c
assert "NEVER decide, speak, or act for these PLAYER characters" in c
assert "AI PLAYERS this session" in c and "characters_act" in c
assert "MAY voice these companions as NPCs" not in c

# player mode, active -> same protection
c = clause("player", "active")
assert "AI PLAYERS this session" in c
assert "MAY voice" not in c

# solo mode -> companions are NPCs the Keeper voices, even in player style
c = clause("player", "solo")
assert "MAY voice these companions as NPCs" in c and ai in c.split("MAY voice")[1]
assert human in c   # human still protected

# cinematic mode -> Keeper may author companions as NPCs even when they could act
c = clause("cinematic", "keeper")
assert "MAY voice these companions as NPCs" in c and ai in c.split("MAY voice")[1]
assert human in c and "real players this session" not in c

# no state -> safe generic fallback (human only)
assert "HUMAN-controlled character" in character_authority_clause(None)

# the clause actually reaches the full system prompt
import rules
from core import campaign as campaign_mod
from core.keeper import build_system_prompt
camp = campaign_mod.load(CAMP)
st.companion_style, st.party_mode = "player", "keeper"
sp = build_system_prompt(camp, rules.get_system("coc7e"), state=st)
assert "NEVER decide, speak, or act for these PLAYER characters" in sp
assert ai in sp

print("test_authority: all checks passed")
