import copy
import hashlib
import json


class ApprovalError(Exception):
    """An action may not run: not approved, changed after approval, or expired."""


def digest(payload: dict) -> str:
    """sha256 of the payload; key order does not matter."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class ApprovalQueue:
    """Agents propose, people approve, only the executor runs: an approved, unchanged payload, once."""

    def __init__(self, send, clock=lambda: 0, ttl: float = 86400):
        self.send = send            # send(payload, idempotency_key) -> result; may raise
        self.clock = clock          # returns the current time in seconds
        self.ttl = ttl              # an approval is valid this long
        self.actions = {}
        self.audit = []

    def _log(self, action_id: str, event: str, by: str, **extra) -> None:
        row = {"action": action_id, "event": event, "by": by}
        row.update(extra)
        self.audit.append(row)

    def propose(self, payload: dict, by: str = "agent") -> str:
        action_id = f"a{len(self.actions) + 1}"
        stored = copy.deepcopy(payload)
        self.actions[action_id] = {
            "payload": stored,
            "hash": digest(stored),
            "status": "proposed",
            "approved_hash": None,
            "approved_at": None,
            "result": None,
        }
        self._log(action_id, "proposed", by)
        return action_id

    def approve(self, action_id: str, by: str, seen_hash: str) -> None:
        action = self.actions[action_id]
        if action["status"] != "proposed":
            raise ApprovalError(f"{action_id} is {action['status']}, not proposed")

        current = digest(action["payload"])
        if seen_hash != current:
            raise ApprovalError(f"{action_id} changed since the reviewer saw it")

        action["hash"] = current
        action["approved_hash"] = current
        action["approved_at"] = self.clock()
        action["status"] = "approved"
        self._log(action_id, "approved", by)

    def reject(self, action_id: str, by: str, reason: str) -> None:
        action = self.actions[action_id]
        if action["status"] == "done":
            raise ApprovalError(f"{action_id} already ran and cannot be rejected")
        action["status"] = "rejected"
        self._log(action_id, "rejected", by, reason=reason)

    def edit(self, action_id: str, payload: dict, by: str) -> None:
        action = self.actions[action_id]
        if action["status"] == "done":
            raise ApprovalError(f"{action_id} already ran and cannot be edited")

        stored = copy.deepcopy(payload)
        action["payload"] = stored
        action["hash"] = digest(stored)
        action["status"] = "proposed"
        action["approved_hash"] = None
        action["approved_at"] = None
        self._log(action_id, "edited", by)

    def execute(self, action_id: str, by: str = "executor"):
        action = self.actions[action_id]

        if action["status"] == "done":
            return action["result"]

        if action["status"] not in ("approved", "failed"):
            raise ApprovalError(f"{action_id} is {action['status']}, not approved")

        approved_at = action["approved_at"]
        if approved_at is None or self.clock() - approved_at > self.ttl:
            action["status"] = "expired"
            raise ApprovalError(f"approval for {action_id} has expired")

        if digest(action["payload"]) != action["approved_hash"]:
            self._log(action_id, "blocked", by)
            raise ApprovalError(f"{action_id} changed after approval")

        try:
            result = self.send(action["payload"], idempotency_key=action_id)
        except Exception:
            action["status"] = "failed"
            self._log(action_id, "failed", by)
            raise

        action["status"] = "done"
        action["result"] = result
        self._log(action_id, "executed", by)
        return result