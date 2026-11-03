from cirdc.web.agent import public_resource, result_status


def test_recovery_keeps_public_feedback_without_internal_error_details():
    value=public_resource({"state":"pending","reason":"resource_recovering","message":"后台服务繁忙，请求高峰期，请重新尝试获取","next_action":"wait","retry_attempts":4,"max_retry_attempts":10,"jobs":[{"id":"attempt","kind":"ieee_pdf","state":"failed","error":"source_route_mismatch","node":"private-node"}]},"12345678","pdf")
    assert value["message"]=="后台服务繁忙，请求高峰期，请重新尝试获取"
    assert value["max_retry_attempts"]==10
    assert "error" not in value["jobs"][0] and "node" not in value["jobs"][0]
    assert result_status({"pdf":value})==202


def test_partial_content_remains_readable_while_recovering_and_exhaustion_ends_waiting():
    waiting=public_resource({"state":"partial","next_action":"wait","jobs":[]},"12345678","content")
    assert waiting["url"].endswith("/content") and result_status({"content":waiting})==202
    exhausted={"state":"failed","next_action":"contact_administrator","message":"后台服务繁忙，请求高峰期，请重新尝试获取","jobs":[]}
    assert result_status({"pdf":exhausted})==200
