-- services/gateway/rate_limit.lua
-- Token Bucket Algorithm implementation for OpenResty/Nginx
local redis = require "resty.redis"
local red = redis:new()

-- 1. Connect to Redis (High Speed)
red:set_timeout(100) -- 100ms timeout
local ok, err = red:connect("rag-redis-prod", 6379)
if not ok then
    ngx.log(ngx.ERR, "failed to connect to redis: ", err)
    return ngx.exit(500)
end

-- 2. Identify Client (IP or API Key)
local client_ip = ngx.var.remote_addr
local key = "rate_limit:" .. client_ip

-- 3. Rate Limit Logic (100 req / minute = ~1.67 tokens/sec, burst up to 100)
local CAPACITY    = 100
local REFILL_RATE = 1.67  -- tokens per second
local TTL         = 3600

-- runs atomically inside Redis via EVAL — no race conditions between read and write
local script = [[
    local capacity    = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local now         = tonumber(ARGV[3])

    local data        = redis.call("HMGET", KEYS[1], "tokens", "last_refill")
    local tokens      = tonumber(data[1]) or capacity  -- nil = new client, start full
    local last_refill = tonumber(data[2]) or now

    -- lazy refill: add tokens for time elapsed since last request, cap at capacity
    tokens = math.min(capacity, tokens + (now - last_refill) * refill_rate)

    local allowed = tokens >= 1 and 1 or 0
    if allowed == 1 then tokens = tokens - 1 end  -- consume one token

    redis.call("HSET", KEYS[1], "tokens", tokens, "last_refill", now)
    redis.call("EXPIRE", KEYS[1], tonumber(ARGV[4]))  -- auto-cleanup idle keys

    return { allowed, math.floor(tokens) }
]]

local result, eval_err = red:eval(script, 1, key, CAPACITY, REFILL_RATE, ngx.now(), TTL)
if not result then
    ngx.log(ngx.ERR, "redis eval failed: ", eval_err)
    return ngx.exit(500)
end

red:set_keepalive(10000, 100)  -- return connection to pool, not close

-- 4. Pass traffic
local allowed, remaining = result[1], result[2]
if allowed == 0 then
    ngx.status = 429
    ngx.say("Rate limit exceeded. Try again later.")
    return ngx.exit(429)
end
-- If we reach here, the request is allowed