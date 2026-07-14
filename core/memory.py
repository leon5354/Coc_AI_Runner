"""Rolling summary compaction. Hard facts live in the state block; this only keeps narrative color."""

COMPACT_THRESHOLD = 30   # compact when messages exceed this
COMPACT_BATCH = 10       # oldest N messages folded into the summary

SUMMARIZE_PROMPT = """You maintain the chronicle of an ongoing tabletop horror game.
Merge the EXISTING CHRONICLE and the NEW EVENTS below into one updated chronicle of at most 350 words.
Structure it as:
1. STORY: established facts, unresolved threads, promises made, NPC dispositions.
2. CHARACTERS: one line PER named character — what happened to them personally
   (injuries, discoveries, fears shown, relationships changed). Never drop a character's line.
Drop: atmospheric prose, dice mechanics, verbatim dialogue.
Respond with the updated chronicle only."""


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
