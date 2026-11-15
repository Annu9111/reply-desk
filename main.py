from fastapi import FastAPI

app = FastAPI(title="Reply Desk")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def home():
    return {"message": "Reply Desk is running"}
