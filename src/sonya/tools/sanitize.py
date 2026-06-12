import re

# Match system/tool instruction markers that could trick the LLM
# into processing them as its own boundaries or tool calls.
# Replaces [TOOL: ...], [DONE...], <think>, </think>, [PRIVATE]
_SANITIZE_RE = re.compile(
    r"(\[\s*(?:TOOL|DONE|PRIVATE|SYSTEM|USER|ASSISTANT|SYSTEM_MESSAGE)[^\]]*\]|<\/?(?:think|thought|system|user|assistant)[^>]*>)",
    re.IGNORECASE,
)

def sanitize_untrusted(text: str) -> str:
    """Neutralize instruction prefixes in untrusted content (web/files)."""
    if not text:
        return text
        
    def _repl(m: re.Match) -> str:
        # replace [ -> (, ] -> )
        # replace < -> (, > -> )
        val = m.group(1)
        val = val.replace("[", "(").replace("]", ")")
        val = val.replace("<", "(").replace(">", ")")
        return val

    return _SANITIZE_RE.sub(_repl, text)
