import re
import time

from agent import FAQ, ORDERS, TOOLS, run
from approvals import ApprovalQueue, digest
from reviewer import gate

SOURCES = list(ORDERS.values()) + list(FAQ.values())


class DemoModel:
    """A rule-based stand-in for the real model, so the demo needs no API key."""

    def next(self, messages):
        task = messages[0]["content"]
        last = messages[-1]

        # Tool results came back: write the draft from them.
        if last["role"] == "user" and isinstance(last["content"], list):
            result = last["content"][0]
            if result["is_error"]:
                text = "Sorry, we could not find that. Could you double-check your order number?"
            elif result["content"].startswith("No FAQ entry"):
                text = "Thanks for reaching out. A team member will follow up with you soon."
            else:
                text = f"Hi! {result['content']} Let us know if you need anything else."
            return {"stop": "end_turn", "text": text, "tokens": 60}

        # First step: pick a tool.
        order = re.search(r"\b[A-Z]\d{3}\b", task)
        if order:
            call = {"name": "lookup_order", "input": {"order_id": order.group(0)}}
        else:
            call = {"name": "search_faq", "input": {"topic": task}}
        return {"stop": "tool_use", "tokens": 40, "calls": [call]}


def demo_writer(task, feedback=None):
    result = run(task, DemoModel(), TOOLS)
    if result["stop"] != "draft_ready":
        return f"[no draft: {result['stop']}]"
    return result["draft"]


class DemoReviewer:
    """A rule-based reviewer. It sees only the draft, the rubric and the sources."""

    def __call__(self, draft, rubric, sources):
        facts = 9 if any(source in draft for source in sources) else 5
        policy = 4 if re.search(r"guarantee|promise|free", draft, re.I) else 10
        fit = 9 if 20 <= len(draft) <= 400 else 5
        clarity = 9 if draft.strip().endswith((".", "!", "?")) else 6

        notes = []
        if facts < 8:
            notes.append("Claims are not backed by the order or FAQ data.")
        if policy < 8:
            notes.append("Do not promise or guarantee anything.")
        if fit < 8:
            notes.append("Keep the reply between 20 and 400 characters.")
        if clarity < 8:
            notes.append("End with a clear, complete sentence.")

        return {
            "scores": {"facts": facts, "policy": policy, "fit": fit, "clarity": clarity},
            "notes": " ".join(notes) or "Looks good.",
        }


class ReplyService:
    def __init__(self):
        self.sent = []
        self.queue = ApprovalQueue(self._send, clock=time.time)
        self.drafts = {}
        self.review_log = []

    def _send(self, payload, idempotency_key):
        # "Sending" only saves the reply to a list. No real email is sent.
        self.sent.append({"action": idempotency_key, "reply": payload["reply"]})
        return "sent"

    def submit(self, message: str) -> dict:
        result = gate(message, demo_writer, DemoReviewer(), SOURCES, log=self.review_log)
        draft_id = f"d{len(self.drafts) + 1}"
        record = {
            "id": draft_id,
            "message": message,
            "draft": result["draft"],
            "review": result["status"],
            "attempts": result["attempts"],
            "scores": result.get("scores"),
            "reason": result.get("reason"),
            "action_id": None,
        }
        if result["status"] == "approved":
            record["action_id"] = self.queue.propose({"reply": result["draft"]})
        self.drafts[draft_id] = record
        return self.view(draft_id)

    def view(self, draft_id: str) -> dict:
        record = self.drafts[draft_id]
        view = {key: record[key] for key in ("id", "message", "draft", "review", "attempts", "scores", "reason")}
        action_id = record["action_id"]
        if action_id is None:
            view["status"] = "held for a person"
            view["hash"] = None
        else:
            action = self.queue.actions[action_id]
            view["status"] = action["status"]
            view["hash"] = digest(action["payload"])
        return view

    def list_drafts(self) -> list:
        return [self.view(draft_id) for draft_id in self.drafts]

    def approve(self, draft_id: str, by: str, seen_hash: str) -> dict:
        action_id = self.drafts[draft_id]["action_id"]
        if action_id is None:
            raise ValueError("this draft was held by the reviewer and cannot be approved")
        self.queue.approve(action_id, by, seen_hash)
        self.queue.execute(action_id)
        return self.view(draft_id)

    def reject(self, draft_id: str, by: str, reason: str) -> dict:
        action_id = self.drafts[draft_id]["action_id"]
        if action_id is None:
            raise ValueError("this draft was held by the reviewer and cannot be rejected")
        self.queue.reject(action_id, by, reason)
        return self.view(draft_id)