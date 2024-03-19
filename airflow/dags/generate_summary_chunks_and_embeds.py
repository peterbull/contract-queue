# Airflow 2.8.2
import json
import logging
import os
import time

import boto3
import botocore
import numpy as np
import pendulum
import tiktoken
from airflow.decorators import dag, task
from app.models.models import Notice, ResourceLink, SummaryChunks
from app.models.schema import NoticeBase, ResourceLinkBase, SummaryChunksBase
from langchain.text_splitter import RecursiveCharacterTextSplitter
from openai import OpenAI
from sqlalchemy import and_, create_engine, exists, insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)

# This is for working in development, on Saturday or Sundary there are little to no posted Notices
# Set this offest to match a weekday to ensure a decent size dataset to work with
# i.e., today is Sunday, so set the offset to `2` to match Notices from Friday.
day_offset = int(os.environ.get("DAY_OFFSET"))

# Database
DATABASE_URL = os.environ.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# S3
S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")
bucket_name = "sam-resource-links-chunks-and-embeds"
aws_prior_date = pendulum.now().subtract(days=day_offset).strftime("%Y%m%d")

# Dates
start_date = pendulum.datetime(2024, 3, 1)
prior_date = pendulum.now().subtract(days=day_offset).strftime("%Y-%m-%d")

# LLM params
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
chunk_size = 200
chunk_overlap = 30
separators = ["\n\n", "\n", " ", ""]


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": start_date,
    "email": ["your-email@example.com"],
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 5,
    "retry_delay": pendulum.duration(minutes=2),
}


@dag(
    catchup=False,
    start_date=start_date,
    schedule=None,
    is_paused_upon_creation=True,
)
def generate_summary_chunks_and_embeds():
    def num_tokens_in_corpus(input: str, encoding_name: str = "gpt-3.5-turbo") -> int:
        encoding = tiktoken.encoding_for_model(encoding_name)
        num_tokens = len(encoding.encode(input))
        return num_tokens

    @task()
    def summary_chunks_to_db():
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )
        with SessionLocal() as db:
            stmt = select(ResourceLink.id, ResourceLink.summary).where(
                ResourceLink.summary.isnot(None)
            )

            results = db.execute(stmt).fetchall()
            data = [dict(result) for result in results]

            for entry in data:
                try:
                    # Check for existing entries
                    stmt = exists().where(SummaryChunks.resource_link_id == entry["id"])
                    is_exists = db.query(stmt).scalar()

                    # Create new entries only if none already exist
                    if not is_exists:
                        split_texts = text_splitter.split_text(entry["summary"])
                        for split_text in split_texts:
                            tokens = num_tokens_in_corpus(split_text)
                            stmt = insert(SummaryChunks).values(
                                chunk_text=split_text,
                                resource_link_id=entry["id"],
                                chunk_tokens=tokens,
                            )
                            db.execute(stmt)
                        db.commit()
                        logging.info(f"Finished committing {len(split_texts)} to db")
                except SQLAlchemyError as e:
                    print(f"A SQLAlchemy error occurred: {e}")
            logging.info(f"No more summaries to chunk")

    @task()
    def get_chunk_embeddings():
        client = OpenAI()
        with SessionLocal() as db:
            stmt = select(SummaryChunks).where(
                and_(SummaryChunks.chunk_text.isnot(None), SummaryChunks.chunk_embedding == None)
            )
            results = db.execute(stmt).scalars().all()
            data = [SummaryChunksBase.model_validate(result) for result in results]

            for entry in tqdm(data):
                try:
                    res = client.embeddings.create(
                        input=entry.chunk_text, model="text-embedding-3-small"
                    )
                    stmt = (
                        update(SummaryChunks)
                        .where(SummaryChunks.id == entry.id)
                        .values(chunk_embedding=res.data[0].embedding)
                    )
                    db.execute(stmt)
                    db.commit()
                except SQLAlchemyError as e:
                    print(f"A SQLAlchemy error occurred: {e}")
                except Exception as e:
                    print(f"An error occurred: {e}")
            logging.info(f"Created embeddings for {len(data)} chunks.")

    @task()
    def chunks_and_embeds_to_s3():
        with SessionLocal() as db:
            stmt = select(
                SummaryChunks.id,
                SummaryChunks.chunk_text,
                SummaryChunks.chunk_tokens,
                SummaryChunks.chunk_embedding,
                SummaryChunks.resource_link_id,
            ).where(SummaryChunks.chunk_embedding.isnot(None))
            results = db.execute(stmt).fetchall()
            data = [dict(result) for result in results]
            # convert ndarrys to list of floats for storage
            for item in data:
                item["chunk_embedding"] = item["chunk_embedding"].tolist()

        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )
        object_name = f"chunk_embeddings/{aws_prior_date}.json"
        try:
            s3_client.head_object(Bucket=bucket_name, Key=object_name)
            logging.info(f"File {object_name} already exists in S3. Skipping upload.")
        except botocore.exceptions.ClientError as e:
            try:
                json_data = json.dumps(data)
                bytes_data = json_data.encode("utf-8")
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_name,
                    Body=bytes_data,
                )
                logging.info(
                    f"Successfully added {object_name} of length: {len(bytes_data)} to S3."
                )
            except botocore.exceptions.ClientError as e:
                print(f"Error: {e}")
                return False

        return True

    chunks_to_db = summary_chunks_to_db()
    update_chunk_embeddings = get_chunk_embeddings()
    push_to_s3 = chunks_and_embeds_to_s3()

    chunks_to_db >> update_chunk_embeddings >> push_to_s3


generate_summary_chunks_and_embeds_dag = generate_summary_chunks_and_embeds()
