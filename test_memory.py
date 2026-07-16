"""Offline memory compaction test. Run: python test_memory.py"""
from core.game_state import GameState
from core.memory import COMPACT_BATCH, COMPACT_THRESHOLD, maybe_compact


class StubLLM:
    def __init__(self, reply="Updated chronicle."):
        self.reply = reply
        self.calls = 0

    def chat(self, messages, system_prompt=None, **kw):
        self.calls += 1
        return self.reply


# below threshold: no compaction
state = GameState(messages=[{"role": "keeper", "content": f"msg {i}"} for i in range(COMPACT_THRESHOLD)])
llm = StubLLM()
assert maybe_compact(state, llm) is False and llm.calls == 0

# above threshold: oldest batch moves to archive, summary updates
state = GameState(messages=[{"role": "keeper", "content": f"msg {i}"} for i in range(COMPACT_THRESHOLD + 5)])
assert maybe_compact(state, StubLLM("The chronicle so far.")) is True
assert len(state.messages) == COMPACT_THRESHOLD + 5 - COMPACT_BATCH
assert len(state.messages_archive) == COMPACT_BATCH
assert state.messages_archive[0]["content"] == "msg 0"      # oldest moved out
assert state.messages[0]["content"] == f"msg {COMPACT_BATCH}"
assert state.summary == "The chronicle so far."

# LLM failure: batch still archived, summary untouched
state = GameState(summary="old", messages=[{"role": "keeper", "content": f"m{i}"} for i in range(40)])
maybe_compact(state, StubLLM("[SYSTEM ERROR] boom"))
assert state.summary == "old" and len(state.messages_archive) == COMPACT_BATCH

print("test_memory: all checks passed")
