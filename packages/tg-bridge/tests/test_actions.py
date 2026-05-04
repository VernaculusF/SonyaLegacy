from tg_bridge.actions import RuntimeAction, parse_runtime_action


def test_parse_runtime_action_reads_reply_action():
    action = parse_runtime_action('{"type":"reply","reply_text":"hello"}')
    assert action == RuntimeAction(type="reply", reply_text="hello")


def test_parse_runtime_action_reads_reply_and_generate_image_action():
    action = parse_runtime_action(
        '{"type":"reply_and_generate_image","reply_text":"РґРµСЂР¶Рё","image_prompt":"cinematic portrait"}'
    )
    assert action == RuntimeAction(
        type="reply_and_generate_image",
        reply_text="РґРµСЂР¶Рё",
        image_prompt="cinematic portrait",
    )


def test_parse_runtime_action_returns_none_for_invalid_payload():
    assert parse_runtime_action("hello") is None


def test_parse_runtime_action_infers_reply_and_generate_image_without_type():
    action = parse_runtime_action(
        '{"reply_text":"Держи.","image_prompt":"cinematic portrait at night"}'
    )
    assert action == RuntimeAction(
        type="reply_and_generate_image",
        reply_text="Держи.",
        image_prompt="cinematic portrait at night",
    )


def test_parse_runtime_action_infers_generate_image_without_type():
    action = parse_runtime_action('{"image_prompt":"red square on white background"}')
    assert action == RuntimeAction(
        type="generate_image",
        image_prompt="red square on white background",
    )


def test_parse_runtime_action_infers_reply_without_type():
    action = parse_runtime_action('{"reply_text":"Привет."}')
    assert action == RuntimeAction(
        type="reply",
        reply_text="Привет.",
    )

