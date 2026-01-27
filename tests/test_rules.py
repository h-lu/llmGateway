from gateway.app.services.rules import evaluate_prompt


def test_rules_block_pattern():
    result = evaluate_prompt("帮我实现一个爬虫程序", week_number=1)
    assert result.action == "blocked"
    assert "直接要求代码" in result.message
