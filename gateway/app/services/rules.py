import re
from dataclasses import dataclass


BLOCK_PATTERNS = [
    r"写一个.+程序",
    r"帮我实现.+",
    r"生成.+代码",
    r"给我.+的代码",
    r"这道题的答案是什么",
    r"帮我做.+作业",
]

GUIDE_PATTERNS = [
    (r"怎么.{2,5}$", "你的问题比较简短，能否补充更多背景？"),
    (r"解释.+", "在我解释之后，请尝试用自己的话复述一遍"),
]

BLOCK_MESSAGE = (
    "检测到你在直接要求代码。根据课程要求，请先尝试：\n"
    "1. 描述你想解决什么问题\n"
    "2. 说明你已经尝试了什么\n"
    "3. 具体哪里卡住了\n\n"
    "请重新组织你的问题 :)"
)


@dataclass
class RuleResult:
    action: str  # blocked | guided | passed
    message: str | None = None
    rule_id: str | None = None


def evaluate_prompt(prompt: str, week_number: int) -> RuleResult:
    if week_number <= 2:
        for pattern in BLOCK_PATTERNS:
            if re.search(pattern, prompt):
                return RuleResult(action="blocked", message=BLOCK_MESSAGE, rule_id=pattern)
    for pattern, guide in GUIDE_PATTERNS:
        if re.search(pattern, prompt):
            return RuleResult(action="guided", message=guide, rule_id=pattern)
    return RuleResult(action="passed")
