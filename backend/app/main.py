import os
from typing import List

import numpy as np
import pandas as pd
from app.db.database import (
    add_naics_code_table,
    create_tables,
    enable_vector_extension,
    get_async_db,
    get_db,
)
from app.models.models import NaicsCodes, Notice, ResourceLink, SummaryChunks
from app.models.schema import (
    NaicsCodeBase,
    NaicsCodeEmbedding,
    NaicsCodeSimple,
    NoticeBase,
    ResourceLinkSimple,
    SummaryChunksSimple,
)
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI, OpenAI
from sqlalchemy import and_, not_, select
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


# def cosine_similarity(a: List[float], b: List[float]) -> float:
#     return round(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)), 4)


@app.get("/")
async def root():
    """
    Health check root endpoint of the application.

    Returns:
        dict: A dictionary with a greeting message.
    """
    return {"Hello": "Claudio", "Hi There": "Rosie"}


@app.get("/naicscodes")
async def get_all_naics_codes(db: AsyncSession = Depends(get_async_db)):
    """
    Retrieve all NAICS codes from the database.

    Parameters:
    - db: AsyncSession - The database session.

    Returns:
    - List[str]: A list of all NAICS codes.
    """
    stmt = select(Notice).distinct()
    result = await db.execute(stmt)
    naics_codes = result.scalars().all()
    return [code.naicsCode.naicsCode for code in naics_codes]


@app.get("/naicscodes/search")
async def search_naics_codes(query: str, db: AsyncSession = Depends(get_async_db)):
    """
    Search for related NAICS codes based on a query string. Query is converted to an embedding
    via an API call to OpenAI.

    Args:
        query (str): The query string to search for.
        db (AsyncSession, optional): The asynchronous database session. Defaults to Depends(get_async_db).

    Returns:
        Tuple[List[NaicsCodeSimple], List[NaicsCodeEmbedding]]: A tuple containing two lists:
            - data: A list of NaicsCodeSimple objects representing the search results.
            - embeddings: A list of NaicsCodeEmbedding objects representing the embeddings of the search results.
    """
    res = await async_client.embeddings.create(input=query, model="text-embedding-3-small")
    query_embed = res.data[0].embedding
    stmt = (
        select(NaicsCodes)
        .order_by(NaicsCodes.description_embedding.l2_distance(query_embed))
        .limit(20)
    )
    result = await db.execute(stmt)
    codes = result.scalars().all()
    data = [NaicsCodeSimple.model_validate(code) for code in codes]
    embeddings = [NaicsCodeEmbedding.model_validate(code) for code in codes]
    return data, embeddings


@app.get("/notices/search/summary_chunks")
async def search_summary_chunks(query: str, db: AsyncSession = Depends(get_async_db)):
    """
    Search for summary chunks based on a query and return the results. Query is converted to an embedding
    via an API call to OpenAI.

    Args:
        query (str): The search query.
        db (AsyncSession, optional): The asynchronous database session. Defaults to Depends(get_async_db).

    Returns:
        Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]: A tuple containing two lists:
            - The first list contains dictionaries representing the search results, with the following keys:
                - "notice_id": the sam.gov id of the notice
                - "summary_chunk": The summary chunk.
                - "summary": The summary.
                - "title": The notice title.
                - "text": The resource link text.
                - "uiLink": The notice UI link.
                - "postedDate": The posted date in ISO format.
            - The second list contains dictionaries representing the embeddings of the summary chunks, with the following key:
                - "chunk_embedding": The embedding of the summary chunk as a list.
    """
    res = await async_client.embeddings.create(input=query, model="text-embedding-3-small")
    query_embed = res.data[0].embedding
    stmt = (
        select(SummaryChunks)
        .order_by(SummaryChunks.chunk_embedding.cosine_distance(query_embed))
        .limit(20)
    )
    results = await db.execute(stmt)
    data = results.scalars().all()
    nearest_chunks = [SummaryChunksSimple.model_validate(item) for item in data]
    chunk_ids = [chunk.id for chunk in nearest_chunks]
    stmt = (
        select(
            Notice.id,
            SummaryChunks.chunk_text,
            ResourceLink.summary,
            Notice.title,
            ResourceLink.text,
            Notice.uiLink,
            Notice.postedDate,
            SummaryChunks.chunk_embedding,
        )
        .join(ResourceLink, Notice.id == ResourceLink.notice_id)
        .join(SummaryChunks, ResourceLink.id == SummaryChunks.resource_link_id)
        .where(SummaryChunks.id.in_(chunk_ids))
    )
    result = await db.execute(stmt)
    data = result.all()
    mapped_data = [
        {
            "notice_id": item[0],
            "summary_chunk": item[1],
            "summary": item[2],
            "title": item[3],
            "text": item[4],
            "uiLink": item[5],
            "postedDate": item[6].isoformat(),
        }
        for item in data
    ]

    embeddings = [{"chunk_embedding": item[7].tolist()} for item in data]

    return mapped_data, embeddings


@app.get("/notices/search/summary")
async def search_summary_chunks(query: str, db: AsyncSession = Depends(get_async_db)):
    """
    Search for summary chunks based on a query. Query is converted to an embedding
    via an API call to OpenAI.

    Args:
        query (str): The search query.
        db (AsyncSession, optional): The async database session. Defaults to Depends(get_async_db).

    Returns:
        tuple: A tuple containing two lists. The first list contains dictionaries with the following keys:
            - "notice_id": the sam.gov id of the notice
            - "summary": The summary of the resource link.
            - "title": The title of the notice.
            - "text": The text of the resource link.
            - "uiLink": The UI link of the notice.
            - "postedDate": The posted date of the notice in ISO format.
        The second list contains dictionaries with the following key:
            - "summary_embedding": The summary embedding of the resource link as a list.
    """
    res = await async_client.embeddings.create(input=query, model="text-embedding-3-small")
    query_embed = res.data[0].embedding
    stmt = (
        select(ResourceLink)
        .order_by(ResourceLink.summary_embedding.cosine_distance(query_embed))
        .limit(20)
    )
    results = await db.execute(stmt)
    data = results.scalars().all()
    nearest_links = [ResourceLinkSimple.model_validate(item) for item in data]
    link_ids = [link.id for link in nearest_links]
    stmt = (
        select(
            Notice.id,
            ResourceLink.summary,
            Notice.title,
            ResourceLink.text,
            Notice.uiLink,
            Notice.postedDate,
            ResourceLink.summary_embedding,
        )
        .join(ResourceLink, Notice.id == ResourceLink.notice_id)
        .where(ResourceLink.id.in_(link_ids))
    )
    result = await db.execute(stmt)
    data = result.all()
    mapped_data = [
        {
            "notice_id": item[0],
            "summary": item[1],
            "title": item[2],
            "text": item[3],
            "uiLink": item[4],
            "postedDate": item[5].isoformat(),
        }
        for item in data
    ]

    embeddings = [{"summary_embedding": item[6].tolist()} for item in data]

    return mapped_data, embeddings


@app.get("/notices/search/{id}/nearby_summaries")
async def search_summary_chunks(id: str, db: AsyncSession = Depends(get_async_db)):

    stmt = (
        select(Notice.id, ResourceLink.summary_embedding, SummaryChunks.chunk_embedding)
        .outerjoin(ResourceLink, Notice.id == ResourceLink.notice_id)
        .outerjoin(SummaryChunks, SummaryChunks.resource_link_id == ResourceLink.id)
        .where(not_(SummaryChunks.chunk_embedding.is_(None)))
        .where(Notice.id == id)
    )
    result = await db.execute(stmt)
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    embeddings_array = np.vstack(
        np.concatenate(df[["summary_embedding", "chunk_embedding"]].values)
    )
    mean_embedding = np.mean(embeddings_array, axis=0)

    return None


@app.get("/notices/naicscode/{naics_code}", response_model=List[NoticeBase])
async def read_notices_by_naics_code(naics_code: int, db: AsyncSession = Depends(get_async_db)):
    stmt = select(Notice).where(Notice.naicsCode.has(naicsCode=naics_code))
    result = await db.execute(stmt)
    notices = result.scalars().all()
    if not notices:
        raise HTTPException(status_code=404, detail="No notices found")
    return [NoticeBase.model_validate(notice) for notice in notices]
