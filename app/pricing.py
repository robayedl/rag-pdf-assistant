from __future__ import annotations

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash":          (0.15,  0.60),
    "gemini-2.5-flash-preview":  (0.15,  0.60),
    "gemini-2.5-pro":            (1.25,  10.00),
    "gemini-2.0-flash":          (0.10,  0.40),
    "sentence-transformers/all-mpnet-base-v2": (0.0, 0.0),
}

_DEFAULT = (0.15, 0.60)


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return cost in USD for a single LLM call."""
    input_rate, output_rate = MODEL_PRICING.get(model, _DEFAULT)
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
