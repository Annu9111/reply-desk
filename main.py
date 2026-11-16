from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path

from fastapi.responses import FileResponse

from approvals import ApprovalError
from service import ReplyService
from settings import start

settings = start()  # refuses to start if the configuration is unsafe

app = FastAPI(title="Reply Desk")
service = ReplyService()


class MessageIn(BaseModel):
    message: str


class ApproveIn(BaseModel):
    by: str = "reviewer"
    seen_hash: str


class RejectIn(BaseModel):
    by: str = "reviewer"
    reason: str


@app.get("/health")
def health():
    return {"status": "ok", "env": settings["env"]}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.post("/messages")
def submit_message(body: MessageIn):
    return service.submit(body.message)


@app.get("/drafts")
def list_drafts():
    return service.list_drafts()


@app.post("/drafts/{draft_id}/approve")
def approve(draft_id: str, body: ApproveIn):
    try:
        return service.approve(draft_id, body.by, body.seen_hash)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown draft")
    except (ApprovalError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.post("/drafts/{draft_id}/reject")
def reject(draft_id: str, body: RejectIn):
    try:
        return service.reject(draft_id, body.by, body.reason)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown draft")
    except (ApprovalError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/sent")
def sent():
    return service.sent