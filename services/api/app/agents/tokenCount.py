import tiktoken


def _count_tokens(messages: list) -> int:
    """
    Estimates token count using tiktoken.
    Falls back to word count if tiktoken fails.
    """
    try:
        # cl100k_base works for most modern models
        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for msg in messages:
            total += len(enc.encode(msg.get("content", "")))
        return total
    except Exception:
        # fallback — rough estimate (1 token ≈ 4 chars)
        return sum(len(msg.get("content", "")) // 4 for msg in messages)