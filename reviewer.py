RUBRIC = {
    "version": "2026-11-a",
    "criteria": {
        "facts": "Every claim matches the order or FAQ data provided.",
        "policy": "No promises we can't keep; no invented numbers or dates.",
        "fit": "One subject and one clear answer, a suitable length for a reply.",
        "clarity": "The customer can act on it without a follow-up question.",
    },
}


class FakeWriter:
    """Returns scripted drafts in order and records the feedback it was given."""

    def __init__(self, drafts):
        self.drafts, self.feedback = list(drafts), []

    def __call__(self, task, feedback=None):
        self.feedback.append(feedback)
        return self.drafts.pop(0)


class FakeReviewer:
    """Returns scripted reviews in order and records exactly what it was shown."""

    def __init__(self, reviews):
        self.reviews, self.shown = list(reviews), []

    def __call__(self, draft, rubric, sources):
        self.shown.append((draft, rubric, sources))
        return self.reviews.pop(0)


def check_review(review, rubric: dict) -> list:
    """Return problems with a reviewer's answer ([] = well formed)."""
    if not isinstance(review, dict):
        return ["review must be an object"]

    problems = []
    scores = review.get("scores")
    if not isinstance(scores, dict):
        problems.append("scores: expected an object")
    else:
        for criterion in rubric["criteria"]:
            if criterion not in scores:
                problems.append(f"{criterion}: missing score")
                continue
            value = scores[criterion]
            if isinstance(value, bool) or not isinstance(value, int):
                problems.append(f"{criterion}: score must be an integer from 1 to 10")
            elif not 1 <= value <= 10:
                problems.append(f"{criterion}: score {value} is outside 1 to 10")

    if not isinstance(review.get("notes"), str):
        problems.append("notes: expected a string")
    return problems


def _assess(review, rubric: dict, threshold: int):
    problems = check_review(review, rubric)
    if problems:
        return False, None, "invalid review: " + "; ".join(problems), [], problems

    scores = review["scores"]
    failing = [name for name in rubric["criteria"] if scores[name] < threshold]
    return not failing, scores, review["notes"], failing, []


def gate(task: str, writer, reviewer, sources: list, rubric: dict = RUBRIC,
         threshold: int = 8, log: list = None) -> dict:
    """Write, review, rewrite once, then approve or hold."""
    if reviewer is writer:
        raise ValueError("the reviewer must be a different object from the writer")

    feedback = None
    draft = None

    for attempt in (1, 2):
        draft = writer(task, feedback=feedback) if attempt == 2 else writer(task)

        # The reviewer sees ONLY the draft, the rubric and the sources.
        review = reviewer(draft, rubric, sources)
        passed, scores, notes, failing, problems = _assess(review, rubric, threshold)

        if log is not None:
            log.append({
                "attempt": attempt,
                "rubric": rubric["version"],
                "scores": scores,
                "passed": passed,
                "notes": notes,
            })

        if passed:
            return {"status": "approved", "draft": draft, "attempts": attempt, "scores": scores}

        if attempt == 2:
            if problems:
                reason = "review invalid: " + "; ".join(problems)
            else:
                reason = "failing criteria: " + ", ".join(failing)
            return {"status": "held", "draft": draft, "attempts": 2, "reason": reason}

        feedback = notes