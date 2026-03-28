from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config

try:
    import database
    from routers.chat import router as chat_router
    from routers.documents import router as documents_router
except ImportError:
    from backend import database
    from backend.routers.chat import router as chat_router
    from backend.routers.documents import router as documents_router

app = FastAPI(title="RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)
app.include_router(chat_router)


@app.on_event("startup")
def on_startup() -> None:
    database.init_db()


@app.get("/")
def health_check():
    return {"status": "ok", "service": "RAG API"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=config.API_HOST, port=config.API_PORT, reload=False)
