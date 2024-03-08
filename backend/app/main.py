from app.db.database import create_tables, get_db
from fastapi import FastAPI

create_tables()
db = get_db()
app = FastAPI()


@app.get("/")
async def root():
    return {"Hello": "Claudio", "Hi There": "Rosie"}
