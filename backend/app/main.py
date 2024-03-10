import os
from typing import List

from app.db.database import (
    add_naics_code_table,
    create_tables,
    enable_vector_extension,
    get_async_db,
    get_db,
)
from app.models.models import NaicsCodes, Notice
from app.models.schema import NaicsCodeSimple, NoticeBase
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Enable vector dtypes for embeddings
enable_vector_extension()

create_tables()
db = get_async_db()
app = FastAPI()
client = OpenAI()
async_client = AsyncOpenAI()

# Add naics code table
add_naics_code_table()


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
async def get_all_naics_codes(db: AsyncSession = Depends(get_async_db)):
    stmt = select(Notice).distinct()
    result = await db.execute(stmt)
    naics_codes = result.scalars().all()
    return [code.naicsCode.naicsCode for code in naics_codes]


@app.get("/naicscodes/search")
async def search_naics_codes(query: str, db: AsyncSession = Depends(get_async_db)):
    res = await async_client.embeddings.create(input=query, model="text-embedding-3-small")
    query_embed = res.data[0].embedding
    stmt = (
        select(NaicsCodes)
        .order_by(NaicsCodes.description_embedding.l2_distance(query_embed))
        .limit(5)
    )
    result = await db.execute(stmt)
    codes = result.scalars().all()
    return [NaicsCodeSimple.model_validate(code) for code in codes]


@app.get("/notices/naicscode/{naics_code}", response_model=List[NoticeBase])
async def read_notices_by_naics_code(naics_code: int, db: AsyncSession = Depends(get_async_db)):
    stmt = select(Notice).where(Notice.naicsCode.has(naicsCode=naics_code))
    result = await db.execute(stmt)
    notices = result.scalars().all()
    if not notices:
        raise HTTPException(status_code=404, detail="No notices found")
    return [NoticeBase.model_validate(notice) for notice in notices]
