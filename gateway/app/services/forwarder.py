import httpx


def forward_chat(base_url: str, api_key: str, payload: dict) -> dict:
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=60) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
