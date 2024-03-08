import os
from typing import List

from app.db.database import create_tables, get_db
from app.models.models import Notice
from app.models.schema import NoticeBase
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

create_tables()
db = get_db()
app = FastAPI()

allowed_origins = os.getenv("ALLOWED_ORIGINS").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["allowed_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Allows all headers
)


@app.get("/")
async def root():
    return {"Hello": "Claudio", "Hi There": "Rosie"}


@app.get("/naicscodes")
async def get_all_naics_codes(db: Session = Depends(get_db)):
    naics_codes = db.query(Notice).distinct().all()
    return [code.naicsCode for code in naics_codes]


@app.get("/notices/{naics_code}", response_model=List[NoticeBase])
def read_notices_by_naics_code(naics_code: int, db: Session = Depends(get_db)):
    notices = db.query(Notice).filter(Notice.naicsCode == naics_code).all()
    if not notices:
        raise HTTPException(status_code=404, detail="No notices found")
    return [NoticeBase.model_validate(notice) for notice in notices]
