"""The no-key brains, without needing them installed. Run: python test_llm.py"""
import json
import os
from types import SimpleNamespace
from unittest import mock

from core.keeper import Keeper, Partial, parse_response
from core.llm_client import LLMClient, LLMError, check_llm, ollama_base

# --- claude_cli: flags, no API key leaks through, result parsing, failures ---
os.environ["ANTHROPIC_API_KEY"] = "must-not-be-used"
with mock.patch("core.llm_client.shutil.which", return_value="claude"):
    c = LLMClient(provider="claude_cli", model_name="sonnet")

seen = {}


def fake_run(cmd, **kw):
    seen.update(cmd=cmd, env=kw["env"], input=kw["input"], system=open(cmd[cmd.index("--system-prompt-file") + 1], encoding="utf-8").read())
    return SimpleNamespace(stdout=json.dumps({"is_error": False, "result": "The door creaks."}), stderr="")


with mock.patch("core.llm_client.subprocess.run", fake_run):
    out = c.chat([{"role": "user", "content": "I open it."}, {"role": "assistant", "content": "Yes?"}], system_prompt="You are the Keeper.")
assert out == "The door creaks."
assert seen["system"] == "You are the Keeper." and "I open it." in seen["input"] and "Yes?" in seen["input"]
assert "ANTHROPIC_API_KEY" not in seen["env"], "must use the plan login, never API billing"
assert seen["cmd"][seen["cmd"].index("--tools") + 1] == "" and "--no-session-persistence" in seen["cmd"]

with mock.patch("core.llm_client.subprocess.run", return_value=SimpleNamespace(
        stdout=json.dumps({"is_error": True, "result": "Not logged in"}), stderr="")):
    out = c.chat([{"role": "user", "content": "x"}])
try:
    check_llm(out)
    raise AssertionError("a login failure must surface as an error")
except LLMError as e:
    assert "Not logged in" in str(e)

# --- ollama: base url forms, context size, no thinking, streaming ---
assert ollama_base("http://localhost:11434/v1") == "http://localhost:11434"
assert ollama_base("http://x:1/") == "http://x:1"
o = LLMClient(provider="ollama", model_name="m")
bodies = []


def fake_post(url, json=None, **kw):
    bodies.append((url, json))
    return SimpleNamespace(status_code=200, text="", json=lambda: {"message": {"content": "<think>hmm</think>Hello."}})


with mock.patch("core.llm_client.requests.post", fake_post):
    assert o.chat([{"role": "user", "content": "x"}], system_prompt="S") == "Hello."
url, body = bodies[0]
assert url.endswith("/api/chat") and body["options"]["num_ctx"] >= 8192 and body["think"] is False


class Resp:
    status_code = 200
    text = ""

    def __enter__(self): return self
    def __exit__(self, *a): pass

    def iter_lines(self):
        for w in ["The ", "door. ", "```json\n", '{"hp_change": null}', "\n```"]:
            yield json.dumps({"message": {"content": w}}).encode()


with mock.patch("core.llm_client.requests.post", return_value=Resp()):
    assert "".join(o.stream([{"role": "user", "content": "x"}])).startswith("The door.")

# the page never sees the control block while the Keeper types
camp = SimpleNamespace(title="T", plot_outline="", endings=[], data={}, rule_system="coc7e", scene=lambda i: {}, clue=lambda i: None)
with mock.patch("core.llm_client.requests.post", return_value=Resp()), \
        mock.patch("core.keeper.build_messages", return_value=[{"role": "user", "content": "x"}]), \
        mock.patch("core.keeper.build_system_prompt", return_value="S"):
    k = Keeper(o, camp, None)
    gen = k.respond_steps(SimpleNamespace(language="auto", god_mode=False), "go")
    shown = []
    try:
        while True:
            shown.append(next(gen))
    except StopIteration as stop:
        narrative, ctrl = stop.value
assert all(isinstance(p, Partial) and "```" not in p.text and "hp_change" not in p.text for p in shown)
assert narrative == "The door." and ctrl == parse_response("x")[1]

with mock.patch("core.llm_client.requests.post", side_effect=OSError("refused")):
    try:
        list(o.stream([{"role": "user", "content": "x"}]))
        raise AssertionError("a dead Ollama must raise")
    except LLMError:
        pass

print("test_llm: all checks passed")
