"""What a call cost, from its token counts.

Anthropic's list prices per million tokens, input and output (the lab's Part 1
table for the 5.5 models). Bedrock publishes its own price page, which is the
one the bill follows, and a regional endpoint costs 10% more than the global one.
"""

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "anthropic.claude-opus-5-5": (4.00, 20.00),
    "anthropic.claude-sonnet-5-5": (2.00, 10.00),
    "anthropic.claude-haiku-5-5": (0.10, 0.50),
    "anthropic.claude-sonnet-4-6": (3.00, 15.00),
    "anthropic.claude-haiku-4-5-20251001-v1:0": (1.00, 5.00),
}

# Cross-region inference profiles ("us.anthropic.…") are priced as the model.
_PROFILE_PREFIXES = ("us.", "eu.", "apac.", "global.")


def cost_usd(model: str, usage: dict[str, int]) -> float | None:
    """Dollars for one parse, or None for a model with no price here."""
    if model.startswith(_PROFILE_PREFIXES):
        model = model.split(".", 1)[1]
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        return None
    input_price, output_price = prices
    total = usage["input_tokens"] * input_price + usage["output_tokens"] * output_price
    return round(total / 1_000_000, 6)
