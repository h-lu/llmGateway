import respx
from httpx import Response

from gateway.app.services.forwarder import forward_chat


@respx.mock
def test_forwarder_calls_upstream():
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=Response(200, json={"id": "x", "choices": []})
    )
    data = forward_chat(
        base_url="https://api.deepseek.com/v1",
        api_key="k",
        payload={"model": "deepseek-chat", "messages": []},
    )
    assert data["id"] == "x"
