from agent import FakeModel, TOOLS, run

# The fake model asks for one tool, then writes the draft.
model = FakeModel([
    {"stop": "tool_use", "tokens": 100,
     "calls": [{"name": "lookup_order", "input": {"order_id": "A100"}}]},
    {"stop": "end_turn", "tokens": 80,
     "text": "Hi! Your order A100 shipped on Nov 10 and arrives on Nov 17. Thanks for your patience."},
])

result = run("Where is my order A100?", model, TOOLS)
print(result)