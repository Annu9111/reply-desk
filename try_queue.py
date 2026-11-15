from approvals import ApprovalError, ApprovalQueue, digest

sent = []


def send(payload, idempotency_key):
    sent.append((idempotency_key, payload["reply"]))
    return "sent"


q = ApprovalQueue(send)

# 1. Nothing runs before approval
a1 = q.propose({"reply": "Your order A100 arrives Nov 17."})
try:
    q.execute(a1)
except ApprovalError as e:
    print("1 blocked before approval:", e)

# 2. Approve, then execute twice: only ONE send
q.approve(a1, "annu", digest(q.actions[a1]["payload"]))
print("2 first execute:", q.execute(a1))
print("2 second execute:", q.execute(a1))
print("2 sent list:", sent)

# 3. Edit after approval: needs a fresh yes
a2 = q.propose({"reply": "Draft two."})
q.approve(a2, "annu", digest(q.actions[a2]["payload"]))
q.edit(a2, {"reply": "Draft two, changed."}, "annu")
try:
    q.execute(a2)
except ApprovalError as e:
    print("3 blocked after edit:", e)

# 4. Reject with a reason
a3 = q.propose({"reply": "Draft three."})
q.reject(a3, "annu", "Too pushy, shorten it.")
print("4 status:", q.actions[a3]["status"])

# 5. Approval expires
now = [0]
q2 = ApprovalQueue(send, clock=lambda: now[0], ttl=60)
a4 = q2.propose({"reply": "Draft four."})
q2.approve(a4, "annu", digest(q2.actions[a4]["payload"]))
now[0] = 120
try:
    q2.execute(a4)
except ApprovalError as e:
    print("5 expired:", e)

print("audit rows in q:", len(q.audit))