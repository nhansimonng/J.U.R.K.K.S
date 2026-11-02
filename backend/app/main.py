import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import get_db
from app.auth import router as auth_router
from app.gyms import router as gyms_router
from app.workout_logs import router as workout_logs_router
from app.workout_plans import router as workout_plans_router
from app.community import router as community_router
from app.reviews import router as reviews_router
from app.foods import router as foods_router
from app.config import CORS_ORIGINS
from app.upload_limit import PhotoBodyLimit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# USDA URLs include a key; do not emit HTTP client URLs in ordinary logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="Pump Check API")
app.add_middleware(PhotoBodyLimit)
app.include_router(auth_router)
app.include_router(gyms_router)
app.include_router(workout_logs_router)
app.include_router(workout_plans_router)
app.include_router(community_router)
app.include_router(reviews_router)
app.include_router(foods_router)

# Lets the frontend (VS Code Live Server) call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Every error comes back as {"error": "message"}, as the contract requires
@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body")
    return JSONResponse(status_code=400, content={"error": f"{field}: {first['msg']}"})


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    logging.getLogger("app").exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "Something went wrong"})


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/health/db")
def db_health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "database connected"}
