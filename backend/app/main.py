from fastapi import FastAPI

app = FastAPI(title="Pump Check API")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}