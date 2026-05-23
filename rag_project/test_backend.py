#!/usr/bin/env python3
"""
Test Backend - Phiên bản đơn giản để debug
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Test Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "✅ Backend hoạt động!"}

@app.get("/api/v1/health")
def health():
    return {"status": "healthy", "message": "Backend sẵn sàng"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)