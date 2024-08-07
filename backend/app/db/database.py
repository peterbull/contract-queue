import json
import logging
import os

import boto3
import pandas as pd
from app.core.config import get_app_settings, get_async_app_settings
from app.models.models import Base, NaicsCodes
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")

DATABASE_URL = get_app_settings().database_conn_string
ASYNC_DATABASE_URL = get_async_app_settings().database_conn_string

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async_engine = create_async_engine(ASYNC_DATABASE_URL)
AsyncSessionLocal = sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

s3_client = boto3.client(
    "s3",
    region_name=S3_REGION_NAME,
    aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
    aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    async with AsyncSessionLocal() as session:
        yield session


def enable_vector_extension():
    with SessionLocal() as session:
        session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        session.commit()


def get_existing_entries(db, model, column):
    return {entry[0] for entry in db.query(column).all()}


def create_new_entries(df, model, existing_entries, **kwargs):
    return [
        model(**{key: row[value] for key, value in kwargs.items()})
        for _, row in df.iterrows()
        if row[kwargs["naicsCode"]] not in existing_entries
    ]


def add_naics_code_table():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    parquet_file_path = os.path.join(
        parent_dir, "data", "naics", "cleaned_combined_naics2022.parquet"
    )

    df = pd.read_parquet(parquet_file_path)
    with SessionLocal() as db:
        try:
            existing_naics_entries = get_existing_entries(db, NaicsCodes, NaicsCodes.naicsCode)
            naics_entries_to_add = create_new_entries(
                df,
                NaicsCodes,
                existing_naics_entries,
                naicsCode="naicsCode",
                title="title",
                description="description",
                description_embedding="description_embedding",
            )

            if naics_entries_to_add:
                db.bulk_save_objects(naics_entries_to_add)
                db.commit()
        except SQLAlchemyError as e:
            print(f"An error occurred while adding NaicsCodes to the database: {e}")
            db.rollback()
