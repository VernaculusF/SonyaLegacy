from tg_bridge.actions import RuntimeAction, RuntimeTaskPayload, parse_runtime_action


def test_parse_runtime_action_reads_reply_action():
    action = parse_runtime_action('{"type":"reply","reply_text":"hello"}')
    assert action == RuntimeAction(type="reply", reply_text="hello")


def test_parse_runtime_action_reads_reply_and_generate_image_action():
    action = parse_runtime_action(
        '{"type":"reply_and_generate_image","reply_text":"держи","image_prompt":"cinematic portrait"}'
    )
    assert action == RuntimeAction(
        type="reply_and_generate_image",
        reply_text="держи",
        image_prompt="cinematic portrait",
    )


def test_parse_runtime_action_reads_create_task_action():
    action = parse_runtime_action(
        """
        {
          "type": "create_task",
          "task_payload": {
            "kind": "workspace_analysis",
            "goal": "Проверить структуру workspace",
            "requested_by_principal": "5785127604",
            "origin_channel": "telegram",
            "origin_chat_id": "5785127604",
            "source_message": "проверь папку",
            "context_summary": "Нужно понять текущую структуру",
            "suggested_steps": ["осмотреть корень", "собрать список узлов"],
            "priority": 4,
            "requires_user_followup": false,
            "followup_prompt": ""
          }
        }
        """
    )
    assert action == RuntimeAction(
        type="create_task",
        task_payload=RuntimeTaskPayload(
            kind="workspace_analysis",
            goal="Проверить структуру workspace",
            requested_by_principal="5785127604",
            origin_channel="telegram",
            origin_chat_id="5785127604",
            source_message="проверь папку",
            context_summary="Нужно понять текущую структуру",
            suggested_steps=("осмотреть корень", "собрать список узлов"),
            priority=4,
            requires_user_followup=False,
            followup_prompt="",
        ),
    )


def test_parse_runtime_action_returns_limitation_for_broken_task_payload():
    action = parse_runtime_action('{"type":"create_task","reply_text":"сейчас разберусь"}')
    assert action == RuntimeAction(
        type="report_limitation",
        reply_text="сейчас разберусь",
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
