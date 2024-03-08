import os

from app.db.database import create_tables, get_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

create_tables()
db = get_db()
app = FastAPI()

allowed_origins = os.getenv("ALLOWED_ORIGINS").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
async def root():
    return {"Hello": "Claudio", "Hi There": "Rosie"}
