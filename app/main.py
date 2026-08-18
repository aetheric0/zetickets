from fastapi import FastAPI

from app.core.deps import db_lifespan

app = FastAPI(
    title="Zetickets Ticketing and Event Management API",
    lifespan=db_lifespan,
    summary="A RESTful API for managing events, tickets, and user authentication.",
    version="1.0.0",
)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "zetickets", "version": app.version}