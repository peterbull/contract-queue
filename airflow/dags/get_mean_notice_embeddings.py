# Airflow 2.8.2
import logging
import os

import boto3
import numpy as np
import pandas as pd
import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
from app.models.models import MeanEmbeddings, Notice, ResourceLink, SummaryChunks
from sqlalchemy import and_, create_engine, exists, insert, not_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)

# This is for working in development, on Saturday or Sundary there are little to no posted Notices
# Set this offest to match a weekday to ensure a decent size dataset to work with
# i.e., today is Sunday, so set the offset to `2` to match Notices from Friday.
day_offset = int(os.environ.get("DAY_OFFSET"))

# Database
DATABASE_URL = os.environ.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

start_date = pendulum.datetime(2024, 3, 1)

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
def get_mean_notice_embeddings():
    @task()
    def get_mean_embeddings_for_notices():
        with SessionLocal() as db:
            stmt = (
                select(Notice.id, ResourceLink.summary_embedding, SummaryChunks.chunk_embedding)
                .outerjoin(ResourceLink, Notice.id == ResourceLink.notice_id)
                .outerjoin(SummaryChunks, SummaryChunks.resource_link_id == ResourceLink.id)
                .where(not_(SummaryChunks.chunk_embedding.is_(None)))
                # .where(Notice.id == "4fd8b2bcb07447889cf8f2bef9b5d07b")
            )

            result = db.execute(stmt)
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
            for notice_id in df["id"].unique():
                df_filtered = df[df["id"] == notice_id]
                embeddings_array = np.vstack(
                    np.concatenate(df_filtered[["summary_embedding", "chunk_embedding"]].values)
                )
                mean_embedding = np.mean(embeddings_array, axis=0)

                mean_embedding_instance = MeanEmbeddings(
                    notice_id=notice_id, mean_embedding=mean_embedding.tolist()
                )
                db.merge(mean_embedding_instance)
            db.commit()

    mean_embeds = get_mean_embeddings_for_notices()


get_mean_notice_embeddings_dag = get_mean_notice_embeddings()
