from fastapi import APIRouter, Depends, Request

from gateway.app.middleware.auth import require_api_key
from gateway.app.services.rules import evaluate_prompt

router = APIRouter()


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, _key=Depends(require_api_key)):
    body = await request.json()
    messages = body.get("messages", [])
    prompt = messages[-1]["content"] if messages else ""
    result = evaluate_prompt(prompt, week_number=1)
    if result.action == "blocked":
        return {
            "choices": [{"message": {"role": "assistant", "content": result.message}}]
        }
    return {"choices": [{"message": {"role": "assistant", "content": "todo"}}]}
