import json


class FakeModel:
    """Stands in for the real model. Returns scripted replies in order and records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def next(self, messages):
        self.seen.append(list(messages))
        assert self.replies, "the fake model ran out of replies: the loop called it too often"
        return self.replies.pop(0)


def call_key(call: dict) -> str:
    """Same tool + same input (key order ignored) -> same key."""
    return call["name"] + ":" + json.dumps(call["input"], sort_keys=True)


def run(task: str, model, tools: dict, max_steps: int = 5, max_tokens: int = 1000) -> dict:
    """A bounded agent loop. Returns {"stop", "steps", "draft", "trace"}."""
    messages = [{"role": "user", "content": task}]
    trace = []
    seen_keys = set()
    total_tokens = 0
    steps = 0

    for step in range(1, max_steps + 1):
        reply = model.next(messages)
        steps = step
        total_tokens += reply.get("tokens", 0)
        messages.append({"role": "assistant", "content": reply})

        stop = reply.get("stop")
        if stop == "refusal":
            return {"stop": "refused", "steps": steps, "draft": None, "trace": trace}
        if stop == "max_tokens":
            return {"stop": "truncated", "steps": steps, "draft": None, "trace": trace}
        if stop == "end_turn":
            return {"stop": "draft_ready", "steps": steps, "draft": reply.get("text"), "trace": trace}

        if stop == "tool_use":
            results = []
            for call in reply.get("calls", []):
                key = call_key(call)
                if key in seen_keys:
                    return {"stop": "loop_detected", "steps": steps, "draft": None, "trace": trace}
                seen_keys.add(key)

                name = call["name"]
                is_error = False
                if name not in tools:
                    content = f"unknown tool '{name}': no tool with that name is available"
                    is_error = True
                else:
                    try:
                        content = str(tools[name](call["input"]))
                    except Exception as exc:
                        content = f"{type(exc).__name__}: {exc}"
                        is_error = True

                trace.append({"step": step, "tool": name, "is_error": is_error})
                results.append({"type": "tool_result", "tool": name, "content": content, "is_error": is_error})

            messages.append({"role": "user", "content": results})

            if total_tokens > max_tokens:
                return {"stop": "budget", "steps": steps, "draft": None, "trace": trace}

    return {"stop": "step_limit", "steps": steps, "draft": None, "trace": trace}


# --- Two demo tools that read from small fake data ---

ORDERS = {
    "A100": "Order A100 shipped on Nov 10 and arrives on Nov 17.",
    "B200": "Order B200 is being packed and ships tomorrow.",
}

FAQ = {
    "refund": "Refunds are issued within 5 business days after we receive the item.",
    "shipping": "Standard shipping takes 3 to 7 business days.",
}


def lookup_order(inp: dict) -> str:
    order_id = inp["order_id"]
    if order_id not in ORDERS:
        raise KeyError(f"no order with id {order_id}")
    return ORDERS[order_id]


def search_faq(inp: dict) -> str:
    topic = inp["topic"].lower()
    for key, answer in FAQ.items():
        if key in topic:
            return answer
    return "No FAQ entry found."


TOOLS = {"lookup_order": lookup_order, "search_faq": search_faq}