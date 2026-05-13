from sonya_runtime.actions.policy import looks_like_task_request, looks_like_task_status_query


def test_policy_detects_task_request_markers():
    assert looks_like_task_request("проверь папку и вернись")
    assert looks_like_task_request("make a plan for this")
    assert not looks_like_task_request("просто ответь на вопрос")


def test_policy_detects_task_status_queries():
    assert looks_like_task_status_query("что с задачей?")
    assert looks_like_task_status_query("task status")
    assert not looks_like_task_status_query("какой у нас план?")
