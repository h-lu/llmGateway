"""Redis Lua scripts for distributed quota management.

These scripts provide atomic operations to prevent TOCTOU race conditions
when checking and consuming quota across multiple instances.
"""

# Lua script for atomic check-and-consume operation with auto-initialization
# This prevents TOCTOU race conditions by checking and incrementing in one atomic operation
# When the key doesn't exist, it starts from 0 automatically (lazy initialization)
# A background sync task ensures Redis state is eventually consistent with the database
CHECK_AND_CONSUME_SCRIPT = """
    local used_key = KEYS[1]
    local meta_key = KEYS[2]
    local current_week_quota = tonumber(ARGV[1])
    local tokens_needed = tonumber(ARGV[2])
    local ttl = tonumber(ARGV[3])
    local student_id = ARGV[4]
    local week_number = ARGV[5]
    local now = ARGV[6]
    
    -- Get current used value (nil returns 0 after tonumber)
    local current = redis.call('GET', used_key)
    local current_used = tonumber(current) or 0
    
    -- Check if quota is available
    local remaining = current_week_quota - current_used
    if remaining < tokens_needed then
        -- Not enough quota, return failure
        return {0, remaining, current_used}
    end
    
    -- Atomically increment (INCRBY creates the key if it doesn't exist)
    local new_used = redis.call('INCRBY', used_key, tokens_needed)
    
    -- Set TTL if this is a newly created key (current was nil)
    if current == nil then
        redis.call('EXPIRE', used_key, ttl)
    end
    
    -- Update metadata (create if doesn't exist)
    local meta = redis.call('GET', meta_key)
    local meta_table = {}
    if meta then
        meta_table = cjson.decode(meta)
    end
    meta_table['quota'] = current_week_quota
    meta_table['last_used'] = now
    meta_table['student_id'] = student_id
    meta_table['week_number'] = week_number
    redis.call('SETEX', meta_key, ttl, cjson.encode(meta_table))
    
    -- Return success with new remaining count
    local new_remaining = current_week_quota - new_used
    return {1, new_remaining, new_used}
"""
