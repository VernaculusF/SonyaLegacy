import re


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _apply_line_formatting(text: str) -> str:
    lines = text.split("\n")
    rendered = []
    for line in lines:
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", line)
        if heading:
            rendered.append(f"<b>{heading.group(1).strip()}</b>")
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet:
            rendered.append(f"- {bullet.group(1)}")
            continue
        rendered.append(line)
    return "\n".join(rendered)


def _apply_inline_formatting(text: str) -> str:
    text = re.sub(r"\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^\n*][\s\S]*?[^\n*]?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__([^\n_][\s\S]*?[^\n_]?)__", r"<b>\1</b>", text)
    text = re.sub(r"(^|[^\w])\*([^*\n][\s\S]*?[^*\n]?)\*(?!\w)", r"\1<i>\2</i>", text)
    text = re.sub(r"(^|[^\w])_([^_\n][\s\S]*?[^_\n]?)_(?!\w)", r"\1<i>\2</i>", text)
    text = re.sub(r"~~([^\n~][\s\S]*?[^\n~]?)~~", r"<s>\1</s>", text)
    return text


def _replace_tokens(text: str, stores: list[str], pattern: str, formatter) -> str:
    regex = re.compile(pattern, re.MULTILINE)

    def repl(match: re.Match[str]) -> str:
        token = f"\u0000TG{len(stores)}\u0000"
        stores.append(formatter(match))
        return token

    return regex.sub(repl, text)


def render_telegram_html(markdown_text: str) -> str:
    source = str(markdown_text or "").replace("\r\n", "\n").strip()
    if not source:
        return ""

    tokens: list[str] = []
    text = _escape_html(source)
    text = _replace_tokens(
        text,
        tokens,
        r"```(?:[a-zA-Z0-9_+-]+)?\n?([\s\S]*?)```",
        lambda match: f"<pre><code>{match.group(1).strip(chr(10))}</code></pre>",
    )
    text = _replace_tokens(
        text,
        tokens,
        r"`([^`\n]+)`",
        lambda match: f"<code>{match.group(1)}</code>",
    )
    text = _apply_line_formatting(text)
    text = _apply_inline_formatting(text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    for idx, token in enumerate(tokens):
        text = text.replace(f"\u0000TG{idx}\u0000", token)
    return text


def chunk_plain_text(text: str, max_len: int = 3500) -> list[str]:
    source = str(text or "").strip()
    if not source:
        return [""]
    if len(source) <= max_len:
        return [source]

    chunks: list[str] = []
    remaining = source
    while len(remaining) > max_len:
        split_at = remaining.rfind("\n\n", 0, max_len + 1)
        if split_at < int(max_len * 0.5):
            split_at = remaining.rfind("\n", 0, max_len + 1)
        if split_at < int(max_len * 0.5):
            split_at = remaining.rfind(" ", 0, max_len + 1)
        if split_at <= 0:
            split_at = max_len
        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks

