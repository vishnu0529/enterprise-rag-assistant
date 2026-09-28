"""Centralised token-cost estimate, the same rates scripts/run_evaluation.py
and scripts/run_golden_set.py already used inline (duplicated in two
places before this). Now also attached as a trace attribute and returned
on every /chat response, not just in batch eval runs.

Illustrative only, NOT official pricing. Update with current provider
rates before relying on this for real cost tracking or billing.
"""

COST_PER_1K_PROMPT_TOKENS_USD = 0.000075
COST_PER_1K_COMPLETION_TOKENS_USD = 0.0003


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1000 * COST_PER_1K_PROMPT_TOKENS_USD
        + completion_tokens / 1000 * COST_PER_1K_COMPLETION_TOKENS_USD
    )
