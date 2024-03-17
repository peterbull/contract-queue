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
day_offset = os.environ.get("DAY_OFFSET")

# Database
DATABASE_URL = os.environ.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# S3
S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")
bucket_name = "sam-resource-links-chunks-and-embeds"
aws_prior_date = pendulum.now().subtract(days=2).strftime("%Y%m%d")

# Dates
start_date = pendulum.datetime(2024, 3, 1)
prior_date = pendulum.now().subtract(days=2).strftime("%Y-%m-%d")

# LLM params
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
chunk_size = 200
chunk_overlap = 30
separators = ["\n\n", "\n", " ", ""]
bs = None  # Set to none to run full batch

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
    is_paused_upon_creation=False,
)
def generate_summary_embeds():
    @task()
    def get_summary_embeddings():
        client = OpenAI()
        with SessionLocal() as db:
            stmt = (
                select(ResourceLink)
                .where(
                    and_(ResourceLink.summary.isnot(None), ResourceLink.summary_embedding == None)
                )
                .limit(bs)
            )
            results = db.execute(stmt).scalars().all()
            data = [ResourceLinkBase.model_validate(result) for result in results]

            for entry in tqdm(data):
                try:
                    res = client.embeddings.create(
                        input=entry.summary, model="text-embedding-3-small"
                    )
                    stmt = (
                        update(ResourceLink)
                        .where(ResourceLink.id == entry.id)
                        .values(summary_embedding=res.data[0].embedding)
                    )
                    db.execute(stmt)
                    db.commit()
                except SQLAlchemyError as e:
                    print(f"A SQLAlchemy error occurred: {e}")
                except Exception as e:
                    print(f"An error occurred: {e}")
            logging.info(f"Created embeddings for {len(data)} chunks.")

    @task()
    def summaries_and_embeds_to_s3():
        with SessionLocal() as db:
            stmt = select(
                ResourceLink.id,
                ResourceLink.summary,
                ResourceLink.summary_tokens,
                ResourceLink.summary_embedding,
                ResourceLink.notice_id,
            ).where(ResourceLink.summary_embedding.isnot(None))
            results = db.execute(stmt).fetchall()
            data = [dict(result) for result in results]
            # convert ndarrys to list of floats for storage
            for item in data:
                item["summary_embedding"] = item["summary_embedding"].tolist()

        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )
        object_name = f"summary_embeddings/{aws_prior_date}.json"
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

    update_summary_embeddings = get_summary_embeddings()
    push_to_s3 = summaries_and_embeds_to_s3()

    update_summary_embeddings >> push_to_s3


generate_summary_embeds_dag = generate_summary_embeds()
