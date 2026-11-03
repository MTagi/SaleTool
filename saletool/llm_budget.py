"""Conservative UTF-8 byte estimate when the provider's tokenizer is unknown."""

import copy
import json


def estimate_input_tokens(payload: dict) -> int:
    # Include schema, tools, and message wrappers; do not assume one character is one token.
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 256


def prepare_payload(payload: dict, context_window: int, default_output: int) -> dict:
    """Preserve the system prompt and JSON structure; truncate only long data strings."""
    prepared = copy.deepcopy(payload)
    prepared.setdefault("max_tokens", default_output)
    available = context_window - int(prepared["max_tokens"]) - 1024

    def shorten(value, limit):
        if isinstance(value, str) and len(value) > limit:
            return value[:limit] + "\n[truncated]"
        if isinstance(value, dict):
            return {key: shorten(item, limit) for key, item in value.items()}
        if isinstance(value, list):
            return [shorten(item, limit) for item in value]
        return value

    for limit in (12000, 6000, 3000, 1500, 750, 384):
        if estimate_input_tokens(prepared) <= available:
            return prepared
        for message in prepared.get("messages", []):
            content = message.get("content")
            if message.get("role") != "user" or not isinstance(content, str):
                continue
            try:
                data = json.loads(content)
            except ValueError:
                # Plain-text prompts have no data boundaries; do not truncate instructions.
                continue
            message["content"] = json.dumps(shorten(data, limit), ensure_ascii=False)
    required = estimate_input_tokens(prepared)
    if required > available:
        raise ValueError(
            f"LLM context budget exceeded: estimated input {required}, available {available}. "
            "Reduce source data or output tokens, or configure the model's context window."
        )
    return prepared
