# Gateway Rules Engine

## Overview
The rules engine evaluates user prompts against configurable regex patterns to block or guide content.

## Rule Service (`app/services/rule_service.py`)

### RuleResult Class
```python
class RuleResult:
    blocked: bool          # If True, content is blocked
    guide: str | None      # Guidance message if applicable
    matched_pattern: str   # The regex that matched
```

### RuleService Class

**Core Methods:**

**`evaluate_prompt(prompt: str) -> RuleResult`**
Synchronous evaluation of prompt against rules.

**`evaluate_prompt_async(prompt: str) -> Coroutine[RuleResult]`**
Async version of evaluation.

**`get_rules() -> List[Rule]`**
Get all rules from database or cache.

**`get_rules_async() -> Coroutine[List[Rule]]`**
Async version of get_rules.

**`reload_rules()`**
Reload rules from database, invalidate cache.

**`reload_rules_async()`**
Async version of reload.

### Hardcoded Rules

**BLOCK_PATTERNS**
Default patterns that block content:
- Direct answer requests
- Code solution requests without learning
- Homework completion requests

**GUIDE_PATTERNS**
Patterns that provide guidance:
- Requests for hints
- Learning-oriented questions
- Concept explanation requests

## Database Model

### Rule Model
```python
class Rule(Base):
    id: Integer (PK)
    name: String
    pattern: String        # Regex pattern
    is_active: Boolean
    rule_type: Enum        # BLOCK or GUIDE
    created_at: DateTime
```

## Evaluation Process

1. Load rules from database (cached in memory)
2. Compile regex patterns with timeout protection
3. Evaluate prompt against patterns in order
4. Return first matching result
5. If no match, content is allowed

## Timeout Protection

**`REGEX_TIMEOUT_SECONDS`:** 5 seconds maximum per regex evaluation

Prevents ReDoS (Regular Expression Denial of Service) attacks by:
- Running regex in separate thread
- Timeout after configured seconds
- Failing closed on timeout

## Cache Strategy

- Rules cached in memory after first load
- Cache invalidated on `reload_rules()` call
- Prevents database queries on every request

## Integration with Chat API

In `app/api/chat.py`:
```python
result = rule_service.evaluate_prompt(prompt)
if result.blocked:
    return create_blocked_response(result.matched_pattern)
```

## Module Functions

**`parse_week_range(week_str: str) -> Tuple[int, int]`
Parse "week X-Y" format.

**`is_week_in_range(week: int, week_range: str) -> bool`
Check if week is in range.

**`evaluate_prompt(prompt: str) -> RuleResult`**
Convenience function using default service.

**`evaluate_prompt_async(prompt: str) -> Coroutine[RuleResult]`**
Async convenience function.

**`reload_rules()`**
Reload rules from database.

**`reload_rules_async()`**
Async reload function.

## Safety Features

1. **Catastrophic Pattern Detection**
   - Detects potentially dangerous regex patterns
   - Warns or blocks patterns that could cause ReDoS

2. **Safe Pattern Compilation**
   - Timeout-protected regex compilation
   - Error handling for invalid patterns

3. **Fail Closed**
   - On evaluation error, defaults to blocking
   - Prevents bypassing filters via malformed input
