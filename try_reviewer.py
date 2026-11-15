from reviewer import FakeReviewer, FakeWriter, gate

good = {"scores": {"facts": 9, "policy": 10, "fit": 9, "clarity": 9}, "notes": "Good."}
bad = {"scores": {"facts": 5, "policy": 10, "fit": 9, "clarity": 9}, "notes": "The arrival date is not in the sources."}

# Case 1: passes first time
log = []
writer = FakeWriter(["Your order A100 arrives Nov 17."])
reviewer = FakeReviewer([good])
print(gate("Where is A100?", writer, reviewer, ["Order A100 arrives Nov 17."], log=log))

# Case 2: fails once, rewrite passes
log2 = []
writer2 = FakeWriter(["It arrives tomorrow!", "Your order A100 arrives Nov 17."])
reviewer2 = FakeReviewer([bad, good])
print(gate("Where is A100?", writer2, reviewer2, ["Order A100 arrives Nov 17."], log=log2))
print("feedback the writer got:", writer2.feedback)

# Case 3: fails twice, so it is held for a person
writer3 = FakeWriter(["It arrives tomorrow!", "It arrives Friday!"])
reviewer3 = FakeReviewer([bad, bad])
print(gate("Where is A100?", writer3, reviewer3, ["Order A100 arrives Nov 17."]))