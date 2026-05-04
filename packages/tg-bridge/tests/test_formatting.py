from tg_bridge.formatting import chunk_plain_text, render_telegram_html


def test_render_telegram_html_formats_headings_code_and_bullets():
    input_text = "**Formatting:**\n\nUse `parse_mode`.\n\n- one\n- two"
    output = render_telegram_html(input_text)
    assert "<b>Formatting:</b>" in output
    assert "<code>parse_mode</code>" in output
    assert "- one" in output


def test_chunk_plain_text_splits_long_text():
    text = "\n\n".join(["a" * 2000, "b" * 2000, "c" * 2000])
    chunks = chunk_plain_text(text, 3500)
    assert len(chunks) == 3
    assert all(len(chunk) <= 3500 for chunk in chunks)

