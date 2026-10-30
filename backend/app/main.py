from fastapi import FastAPI

from app.api import auth, health, me

app = FastAPI(title="WordPath API", version="0.1.0")

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api")
app.include_router(me.router, prefix="/api")
