# Gateway Rules Engine

## Purpose
Content filtering system to guide student learning behavior by blocking or modifying requests based on prompt patterns.

## Database Model
```python
class Rule(Base):
    id: int
    pattern: str          # Regex pattern to match
    rule_type: str        # "block" or "guide"
    message: str          # Response message or guidance
    active_weeks: str     # Week range like "1-2" or "3-6"
    enabled: bool         # Active/inactive
```

## Rule Types

### Block Rules (`rule_type = "block"`)
- Immediately returns a blocking message
- No API call is made
- Logged with action="blocked"
- Example: Block direct "write code" requests in early weeks

### Guide Rules (Deprecated)
- Originally prepended guidance to system prompt
- Now replaced by `WeeklySystemPrompt` feature
- Kept for backward compatibility

## Rule Service (`app/services/rule_service.py`)

### Key Functions

#### `evaluate_prompt(prompt: str, week_number: int) → RuleResult`
```python
class RuleResult:
    action: str      # "allow", "blocked", "guided"
    message: str | None
    rule_id: int | None
```

Flow:
1. Load all enabled rules from database
2. Filter rules where `week_number` is in `active_weeks`
3. Match prompt against each rule's pattern (regex)
4. Return first matching rule's result
5. If no match, return `RuleResult(action="allow")`

#### `parse_week_range(range_str: str) → list[int]`
Parses week range strings:
- `"1-3"` → `[1, 2, 3]`
- `"5"` → `[5]`
- `"1-2,4-5"` → `[1, 2, 4, 5]`

#### `is_week_in_range(week_number: int, range_str: str) → bool`
Check if week is in the rule's active range.

## Rule Matching Rules
1. Rules are evaluated in database ID order
2. First matching rule wins (short-circuit)
3. Regex patterns are case-sensitive
4. Pattern matching uses Python `re.search()`

## Example Rules
```sql
-- Block "give me code" requests in weeks 1-2
INSERT INTO rules (pattern, rule_type, message, active_weeks, enabled)
VALUES ('.*给我.*代码.*|.*write.*code.*', 'block', 
        '请先描述问题，不要直接要代码', '1-2', true);

-- Guide requests in weeks 3-6 (deprecated)
INSERT INTO rules (pattern, rule_type, message, active_weeks, enabled)
VALUES ('.*help.*', 'guide', 
        'Remember to explain your thinking first', '3-6', true);
```

## Weekly System Prompts (Preferred)
Modern approach uses `WeeklySystemPrompt` table instead of guide rules:
- `week_start`, `week_end` - Week range
- `system_prompt` - Full system prompt
- Injected via `inject_weekly_system_prompt()`
- Supports progressive learning

## Backward Compatibility
- Old hardcoded `BLOCK_PATTERNS` and `GUIDE_PATTERNS` kept as fallback
- Database rules take precedence over hardcoded patterns
- `app/services/rules.py` re-exports from `rule_service.py`

## Configuration
Rules are stored in database, managed via admin API:
- `GET /api/rules` - List all rules
- `POST /api/rules` - Create rule
- `PUT /api/rules/{id}` - Update rule
- `DELETE /api/rules/{id}` - Delete rule
