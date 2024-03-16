# Airflow 2.8.2
import json
import logging
import os
import time

import anthropic
import boto3
import botocore
import pendulum
from airflow.decorators import dag, task
from app.models.models import Notice, ResourceLink
from app.models.schema import NoticeBase, ResourceLinkBase
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from typing_extensions import List, Optional

logging.basicConfig(level=logging.INFO)

# Database
DATABASE_URL = os.environ.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# S3
S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")
bucket_name = "sam-resource-links-haiku-summaries"

# Dates
start_date = pendulum.datetime(2024, 3, 1)
prior_date = pendulum.now().subtract(days=1).strftime("%Y-%m-%d")

# LLM params
client = anthropic.Anthropic()
bs = 5
max_input_tokens = 5000  # This number has to be very low right now, Anthropic API caps out at 1,000,000 tokens daily for the lowest tier currently
max_output_tokens = 1000
model = "claude-3-haiku-20240307"
temperature = 0.0


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
    # schedule=None,
    is_paused_upon_creation=False,
)
def generate_summaries_from_claude():
    @task()
    def get_resources_without_summaries(prior_date: str, max_input_tokens: int):
        with SessionLocal() as db:
            stmt = text(
                """select text from resource_links 
                            where notice_id in 
                                (select id from notices
                                    where
                                    naics_code_id = 
                                        (select id from naics_codes where \"naicsCode\" = 236220)
                                        and
                                        \"postedDate\" = :prior_date)
                            and 
                            text != 'unparsable' 
                            and
                            text != 'adobe-error'
                            and
                            text != 'encoding-error'
                            and
                            text is not null
                            and
                            file_tokens < :max_input_tokens
                        """
            )
            results = (
                db.execute(
                    stmt, params={"prior_date": prior_date, "max_input_tokens": max_input_tokens}
                )
                .scalars()
                .all()
            )

        return results

    @task()
    def claude_text_summarization(
        client: anthropic.Anthropic,
        doc_texts: str,
        max_output_tokens: int = 1000,
        temperature: float = 0.0,
        model: str = "claude-3-haiku-20240307",
    ):
        system = (
            "You are a highly skilled AI trained to analyze text and summarize it very succinctly."
        )
        messages = [
            {
                "role": "user",
                "content": f"""Analyze the provided government contracting document to extract key information that will help contractors assess whether the project aligns with their capabilities and is worth pursuing. Focus on the following aspects:

                1. Scope of Work: What specific services or products does the project require?
                2. Special Equipment Needed: Are there unique tools or machinery necessary for project completion?
                3. Domain of Expertise Required: What specialized knowledge or skills are needed?
                4. Contractor Workforce Size: Estimate the workforce size needed to meet project demands.

                Additionally, consider these factors to further refine suitability assessment:
                - Project Duration: How long is the project expected to last?
                - Location and Logistics: Where is the project located, and are there significant logistical considerations?
                - Budget and Payment Terms: What is the budget range, and how are payments structured?
                - Compliance and Regulations: Are there specific industry regulations or standards to comply with?
                - Past Performance Requirements: Is prior experience in similar projects a prerequisite?

                Summarize these elements in no more than 25 sentences to provide a comprehensive overview, enabling contractors to quickly determine project compatibility and feasibility. Highlight any potential challenges or requirements that may necessitate additional considerations.
                Text is below:
                {text}
                """,
            },
        ]

        with SessionLocal() as db:
            for doc_text in tqdm(doc_texts):
                try:
                    res = client.messages.create(
                        model=model,
                        max_tokens=max_output_tokens,
                        temperature=temperature,
                        system=system,
                        messages=messages,
                    )
                except anthropic.APIConnectionError as e:
                    logging.error("The server could not be reached")
                    logging.error(e.__cause__)
                    continue
                except anthropic.RateLimitError as e:
                    logging.error("A 429 status code was received; we should back off a bit.")
                    time.sleep(60)  # sleep for 60 seconds
                    continue
                except anthropic.APIStatusError as e:
                    logging.error("Another non-200-range status code was received")
                    logging.error(f"Status code: {e.status_code}")
                    logging.error(f"Response: {e.response}")
                    continue

                try:
                    stmt = (
                        update(ResourceLink)
                        .where(ResourceLink.id == doc_text[0])
                        .values(summary=res.content[0].text, summary_tokens=res.usage.output_tokens)
                    )
                    db.execute(stmt)
                    db.commit()
                except SQLAlchemyError as e:
                    logging.error("An error occurred while updating the database.")
                    logging.error(e)
                    continue

                logging.info(
                    f"Succesfully summarized {res.usage.input_tokens} token document in {res.usage.input_tokens} tokens"
                )

    @task()
    def backup_summaries_to_s3(bucket_name: str = bucket_name, prior_date: str = prior_date):
        with SessionLocal() as db:
            stmt = (
                select(ResourceLink.notice_id, ResourceLink.summary)
                .join(Notice, ResourceLink.notice_id == Notice.id)
                .where(Notice.postedDate == prior_date)
            )
            results = db.execute(stmt)
            data = [{"notice_id": result[0], "summary": result[1]} for result in results]

        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )
        object_name = f"{bucket_name}/{prior_date}.json"
        try:
            json_data = json.dumps(data)
            bytes_data = json_data.encode("utf-8")
            s3_client.put_object(
                Bucket=bucket_name,
                Key=object_name,
                Body=bytes_data,
            )
            logging.info(f"Successfully added {object_name} of length: {len(bytes_data)} to S3.")

        except botocore.exceptions.ClientError as e:
            print(f"Error: {e}")
            return False

        return True

    resources_to_summarize = get_resources_without_summaries(
        prior_date=prior_date, max_input_tokens=max_input_tokens
    )
    claude_text_summarization(client=client, doc_texts=resources_to_summarize)
