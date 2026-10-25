import math


def estimate_tokens_by_chars(text: str) -> int:
    """Rough token count: ~4 characters per token for English text.

    Good enough to budget with; it under-counts code and non-Latin scripts. The same rule is
    used to backfill token_count in migration 0003, so keep the two in step.
    """
    return math.ceil(len(text) / 4)
