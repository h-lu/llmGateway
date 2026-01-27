from fastapi.testclient import TestClient

from gateway.app.main import app


def test_chat_flow_blocked():
    client = TestClient(app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        json={"messages": [{"role": "user", "content": "帮我实现一个爬虫程序"}]},
    )
    assert resp.status_code == 200
    assert "直接要求代码" in resp.json()["choices"][0]["message"]["content"]
