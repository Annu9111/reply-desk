from fastapi import FastAPI

from settings import start

settings = start()  # refuses to start if the configuration is unsafe

app = FastAPI(title="Reply Desk")


@app.get("/health")
def health():
    return {"status": "ok", "env": settings["env"]}


@app.get("/")
def home():
    return {"message": "Reply Desk is running"}