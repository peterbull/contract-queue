# Airflow 2.8.2
import logging
import os
import re
import tempfile
from zipfile import BadZipfile

import anthropic
import pendulum
import requests
import textract
import tiktoken
from airflow.decorators import dag, task
from app.models.models import (
    Link,
    NaicsCodes,
    Notice,
    OfficeAddress,
    PlaceOfPerformance,
    PointOfContact,
    ResourceLink,
)
from app.models.schema import NoticeBase, ResourceLinkBase
from sqlalchemy import and_, create_engine, or_, select, text, update, values
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from typing_extensions import List, Optional

logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.environ.get("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
start_date = pendulum.datetime(2024, 3, 1)

# params
prior_date = pendulum.now().subtract(days=1).strftime("%Y-%m-%d")

client = anthropic.Anthropic()
bs = 5
max_input_tokens = 50000
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
    schedule="0 6 * * *",
    # schedule=None,
    is_paused_upon_creation=True,
)
def generate_summaries_from_claude():
    @task()
    def get_items_without_summaries(prior_date: str, max_input_tokens: int):
        with SessionLocal() as db:
            stmt = text(
                """select id, text, notice_id from resource_links 
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
            results = db.execute(
                stmt, params={"prior_date": prior_date, "max_input_tokens": max_input_tokens}
            ).all()

        return results

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
            for doc_text in doc_texts:
                res = client.messages.create(
                    model=model,
                    max_tokens=max_output_tokens,
                    temperature=temperature,
                    system=system,
                    messages=messages,
                )
                stmt = (
                    update(ResourceLink)
                    .where(ResourceLink.id == doc_text[0])
                    .values(summary=res.content[0].text, summary_tokens=res.usage.output_tokens)
                )
                db.excute(stmt)
                db.commit()
                logging.info(
                    f"Succesfully summarized {res.usage.input_tokens} token document in {res.usage.input_tokens} tokens"
                )
