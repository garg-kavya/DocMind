"""
Rate Limiting Middleware
=========================

Purpose:
    Prevents API abuse by limiting request rates per client IP.
    Particularly important for the query endpoints which trigger
    OpenAI API calls (and thus cost money).

Strategy:
    Token bucket algorithm per client IP:
    - Upload endpoint: 10 requests/minute
    - Query endpoint: 30 requests/minute
    - Session endpoints: 60 requests/minute
    - Health endpoint: unlimited

Response on Rate Limit:
    429 Too Many Requests
    {
        "detail": "Rate limit exceeded. Try again in {retry_after} seconds.",
        "retry_after": int
    }
    Headers:
        X-RateLimit-Limit: max requests per window
        X-RateLimit-Remaining: requests remaining
        X-RateLimit-Reset: epoch seconds when the window resets
        Retry-After: seconds until next request allowed

Dependencies:
    - fastapi (Request, Response)
    - time (stdlib)
    - collections (stdlib) — for token bucket state
"""
