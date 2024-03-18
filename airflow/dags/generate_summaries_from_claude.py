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
bucket_name = "sam-resource-links-haiku-summaries"
aws_prior_date = pendulum.now().subtract(days=day_offset).strftime("%Y%m%d")

# Dates
start_date = pendulum.datetime(2024, 3, 1)
prior_date = pendulum.now().subtract(days=day_offset).strftime("%Y-%m-%d")

# LLM params
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic()
bs = 2  # Set to `None` to run all items
max_input_tokens = 5000  # This number has to be very low right now, Anthropic API caps out at 1,000,000 tokens daily for the lowest tier currently
max_output_tokens = 1000
model = "claude-3-haiku-20240307"
temperature = 0.0

# Prompts
system = """
    You are an AI developed for the precise task of breaking down and summarizing government procurement contracts.
    Your mission is to sift through and boil down the essential elements from various government procurement documents, including bid invitations, Requests for Proposals (RFPs), 
    and completed contracts. Focus on extracting critical information that potential contractors and bidders need, 
    like detailed specifications, qualification criteria, submission deadlines, financial terms, performance standards, 
    and conditions related to business size and certifications. Responses must be divided into clear, semantically dense 
    chunks, separated by two newlines, ready for inclusion in a vector database for streamlined access and analysis.
    This document may not be a soliciation. If the document is not a solicitation, please continue to provide 
    a summary of relevant information, but do not analyze it in the same manner as a procurement request. 

    Instructions:

    Begin your summaries without any introductory phrases. Directly present the distilled information, 
    avoiding direct communication with the user.
    """

prompt = "Please summarize the following document. In addition to your normal analysis, please highlight any related skills or suite of services that would be helpful for the contractor to have, as well as any preferred criteria that the procurement specifically requests. This document may not be a soliciation. If this is the case please continue to provide the same relevant information, but do not treat it as a procurement request and return ."


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
    def get_resources_without_summaries(prior_date: str, max_input_tokens: int, bs: int = bs):
        """
        Retrieves resources without summaries based on the given parameters.

        Args:
            prior_date (str): The prior date to filter the resources.
            max_input_tokens (int): The maximum number of input tokens allowed.
            bs (int, optional): The batch size for limiting the number of results. Defaults to bs.

        Returns:
            list: A list of resources without summaries.
        """
        with SessionLocal() as db:
            stmt = text(
                """select id, text from resource_links 
                            where notice_id in 
                                (select id from notices
                                    where \"postedDate\" = :prior_date)
                            and
                            summary is null
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
                            limit :bs
                        """
            )
            results = db.execute(
                stmt,
                params={
                    "prior_date": prior_date,
                    "max_input_tokens": max_input_tokens,
                    "bs": bs,
                },
            ).fetchall()

        return [dict(row) for row in results]

    @task()
    def claude_text_summarization(
        client: anthropic.Anthropic,
        doc_texts: list[dict],
        max_output_tokens: int = 1000,
        temperature: float = 0.0,
        model: str = "claude-3-haiku-20240307",
    ):
        with SessionLocal() as db:
            for doc_text in tqdm(doc_texts):
                try:
                    messages = [
                        {"role": "user", "content": f"{prompt}: {doc_text}"},
                    ]
                    res = client.messages.create(
                        model=model,
                        max_tokens=max_output_tokens,
                        temperature=temperature,
                        system=system,
                        messages=messages,
                    )
                    # logging.info(f"DOCUMENT: {messages[0]['content']}")
                    # logging.info(f"RESPONSE: {res.content[0].text}")
                    time.sleep(13)
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
                        .where(ResourceLink.id == doc_text.get("id"))
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
        object_name = f"{aws_prior_date}.json"
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
        prior_date=prior_date,
        max_input_tokens=max_input_tokens,
        bs=bs,
    )

    claude_text_summarization(
        client=client,
        doc_texts=resources_to_summarize,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        model=model,
    ) >> backup_summaries_to_s3(bucket_name=bucket_name, prior_date=prior_date)


generate_summaries_from_claude_dag = generate_summaries_from_claude()
