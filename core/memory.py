"""Rolling summary compaction. Hard facts live in the state block; this only keeps narrative color."""

COMPACT_THRESHOLD = 30   # compact when messages exceed this
COMPACT_BATCH = 10       # oldest N messages folded into the summary
THOUGHT_WINDOW = 12      # verbatim inner monologue kept; older thoughts distil into memory_summary

SUMMARIZE_PROMPT = """You maintain the chronicle of an ongoing tabletop horror game.
Merge the EXISTING CHRONICLE and the NEW EVENTS below into one updated chronicle of at most 350 words.
Structure it as:
1. STORY: established facts, unresolved threads, promises made, NPC dispositions.
2. CHARACTERS: one line PER named character — what happened to them personally
   (injuries, discoveries, fears shown, relationships changed). Never drop a character's line.
Drop: atmospheric prose, dice mechanics, verbatim dialogue.
Respond with the updated chronicle only."""


CHARACTER_MEMORY_PROMPT = """You maintain ONE character's private memory in a tabletop horror game.
Rewrite their memory in FIRST PERSON, in their own voice, from the material below.

Respond in exactly this format:

MEMORY:
<at most 200 words: what I have lived through and what it did to me — what I saw and did
myself, what I learned, what frightened or hardened me, what I still intend to do. Keep
older memories that still matter; drop trivia. This is my life, not a report of the plot.>

RELATIONSHIPS:
<Name>: <one line — what I privately think of them now, and why>
(one line per person I have an opinion about; omit this section if I have none)"""


def compact_character(char, llm) -> bool:
    """Fold a character's overflowing thoughts into their personal memory + relationships.
    Cheap: runs only when their inner monologue outgrows the window."""
    if len(char.private_thoughts) <= THOUGHT_WINDOW:
        return False
    old, char.private_thoughts = (char.private_thoughts[:-THOUGHT_WINDOW],
                                  char.private_thoughts[-THOUGHT_WINDOW:])
    rels = "\n".join(f"{k}: {v}" for k, v in char.relationships.items()) or "(none yet)"
    prompt = (f"I am {char.name}. {char.personality}\n"
              f"My history: {char.backstory}\n\n"
              f"MY MEMORY SO FAR:\n{char.memory_summary or '(nothing yet)'}\n\n"
              f"WHAT I THINK OF THE OTHERS:\n{rels}\n\n"
              f"MY THOUGHTS SINCE THEN (oldest first):\n" + "\n".join(f"- {t}" for t in old))
    out = llm.chat([{"role": "user", "content": prompt}],
                   system_prompt=CHARACTER_MEMORY_PROMPT, temperature=0.4, max_tokens=450)
    if not out or out.startswith("[SYSTEM ERROR]"):
        return False  # ponytail: on failure the thoughts are gone but memory_summary is intact

    body = out.strip()
    mem, _, rel_block = body.partition("RELATIONSHIPS:")
    mem = mem.replace("MEMORY:", "", 1).strip()
    if mem:
        char.memory_summary = mem
    for line in rel_block.strip().splitlines():
        name, sep, opinion = line.partition(":")
        if sep and opinion.strip():
            char.relationships[name.strip().lstrip("-* ")] = opinion.strip()
    return True


def maybe_compact(state, llm) -> bool:
    """Fold the oldest messages into state.summary when the transcript grows. Returns True if compacted."""
    if len(state.messages) <= COMPACT_THRESHOLD:
        return False
    batch, state.messages = state.messages[:COMPACT_BATCH], state.messages[COMPACT_BATCH:]
    state.messages_archive.extend(batch)
    events = "\n".join(f"[{m['role']}{':' + m['name'] if m.get('name') else ''}] {m['content']}" for m in batch)
    prompt = f"EXISTING CHRONICLE:\n{state.summary or '(none yet)'}\n\nNEW EVENTS:\n{events}"
    result = llm.chat([{"role": "user", "content": prompt}],
                      system_prompt=SUMMARIZE_PROMPT, temperature=0.3, max_tokens=500)
    if result and not result.startswith("[SYSTEM ERROR]"):
        state.summary = result.strip()
    # ponytail: on LLM failure the batch stays archived but unsummarized — acceptable loss, facts live in state
    return True
