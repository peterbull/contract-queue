# Airflow 2.8.2
import json
import logging
import os

import boto3
import pendulum
import requests
from airflow.datasets import Dataset
from airflow.decorators import dag, task
from airflow.operators.empty import EmptyOperator
from app.core.config import get_app_settings
from app.models.models import (
    Link,
    NaicsCodes,
    Notice,
    OfficeAddress,
    PlaceOfPerformance,
    PointOfContact,
    ResourceLink,
)
from botocore.exceptions import ClientError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SAM_PUBLIC_API_KEY = os.environ.get("SAM_PUBLIC_API_KEY")
S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")

logging.basicConfig(level=logging.INFO)

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

previous_date = pendulum.now("utc").subtract(days=1).strftime("%Y%m%d")
bucket_name = "sam-gov-opportunities"
file_name = f"daily-opportunity-posts/{previous_date}.json"
daily_notices = Dataset(f"s3://{bucket_name}/{file_name}")


def parse_date(iso_str):
    try:
        return pendulum.parse(iso_str)
    except (pendulum.parser.exceptions.ParserError, TypeError, ValueError):
        return None


@dag(
    catchup=False,
    start_date=start_date,
    schedule="@daily",
    tags=["produces", "dataset-scheduled"],
    is_paused_upon_creation=False,
)
def ingest_opportunities_to_s3(bucket_name, file_name):

    # Using previous date until the time that new info is posted becomes known
    previous_date = pendulum.now("utc").subtract(days=1).strftime("%Y%m%d")
    formatted_request_date = pendulum.parse(previous_date, strict=False).format("MM/DD/YYYY")
    base_url = "https://api.sam.gov/opportunities/v2/search"

    api_params = {
        "api_key": SAM_PUBLIC_API_KEY,
        "postedFrom": formatted_request_date,
        "postedTo": formatted_request_date,
        "ptype": "o",
        "limit": 1000,
        "offset": 0,
    }

    @task.branch()
    def check_existing_data(bucket_name, file_name):
        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )
        try:
            s3_client.head_object(Bucket=bucket_name, Key=file_name)
            logging.info(f"File {file_name} exists in bucket {bucket_name}")
            return "end_dag"
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logging.info(f"File {file_name} does not exist in bucket {bucket_name}")
                return "get_new_opportunities"
            else:
                raise

    @task()
    def get_new_opportunities(base_url, api_params):
        opportunities = []

        while True:
            res = requests.get(base_url, params=api_params)
            if res.status_code == 200:
                data = res.json()
                records = data.get("opportunitiesData", [])
                opportunities.extend(records)

                if len(records) < api_params["limit"]:
                    print(f"Finished with {len(opportunities)} records in memory")
                    break

                api_params["offset"] += api_params["limit"]
            elif res.status_code == 429:
                logging.warning("Request limit hit -- try again in 24 hours")
                break
            else:
                raise Exception(f"Request failed with status code {res.status_code}")
        return opportunities

    @task(
        outlets=[daily_notices],
    )
    def opportunity_obj_to_s3(opportunities, bucket_name, file_name):
        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )

        json_data = json.dumps(opportunities)
        bytes_data = json_data.encode("utf-8")

        s3_client.put_object(Bucket=bucket_name, Key=file_name, Body=bytes_data)
        logging.info(f"Successfully wrote to S3 bucket {bucket_name} with key {file_name}")

    end_dag = EmptyOperator(task_id="end_dag")
    check_result = check_existing_data(bucket_name, file_name)
    new_opportunities = get_new_opportunities(base_url, api_params)
    stored_opportunities_dataset = opportunity_obj_to_s3(new_opportunities, bucket_name, file_name)

    check_result >> [new_opportunities, end_dag]
    new_opportunities >> stored_opportunities_dataset


ingest_opportunities_to_s3_dag = ingest_opportunities_to_s3(bucket_name, file_name)


@dag(
    start_date=start_date,
    tags=["consumes", "dataset-triggered"],
    schedule=[daily_notices],
    is_paused_upon_creation=False,
)
def s3_opportunities_to_postgres(bucket_name, file_name):
    @task()
    def get_opportunities_from_s3(bucket_name, file_name):
        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )
        s3_response = s3_client.get_object(Bucket=bucket_name, Key=file_name)
        s3_response = s3_response["Body"].read().decode("utf-8")
        return json.loads(s3_response)

    @task()
    def commit_new_opportunities_to_postgres(s3_response):
        with SessionLocal() as session:
            notices_added = 0
            for notice_data in s3_response:
                notice_id = notice_data.get("noticeId")
                exists = session.query(Notice.id).filter_by(id=notice_id).scalar() is not None
                if exists:
                    continue  # skipping the loop if the noticeId is already in the db

                office_address = None
                office_address_data = notice_data.get("officeAddress", {})
                if office_address_data:
                    office_address = OfficeAddress(
                        zipcode=office_address_data.get("zipcode", None),
                        city=office_address_data.get("city", None),
                        countryCode=office_address_data.get("countryCode", None),
                        state=office_address_data.get("state", None),
                    )

                place_of_performance = None
                place_of_performance_data = notice_data.get("placeOfPerformance", {})
                if place_of_performance_data:
                    place_of_performance = PlaceOfPerformance(
                        city_code=place_of_performance_data.get("city", {}).get("code", None),
                        city_name=place_of_performance_data.get("city", {}).get("name", None),
                        state_code=place_of_performance_data.get("state", {}).get("code", None),
                        state_name=place_of_performance_data.get("state", {}).get("name", None),
                        country_code=place_of_performance_data.get("country", {}).get("code", None),
                        country_name=place_of_performance_data.get("country", {}).get("name", None),
                    )

                notice = Notice(
                    id=notice_data.get("noticeId"),
                    title=notice_data.get("title"),
                    solicitationNumber=notice_data.get("solicitationNumber"),
                    fullParentPathName=notice_data.get("fullParentPathName"),
                    fullParentPathCode=notice_data.get("fullParentPathCode"),
                    postedDate=parse_date(notice_data.get("postedDate")),
                    type=notice_data.get("type"),
                    baseType=notice_data.get("baseType"),
                    archiveType=notice_data.get("archiveType"),
                    archiveDate=parse_date(notice_data.get("archiveDate")),
                    typeOfSetAsideDescription=notice_data.get("typeOfSetAsideDescription"),
                    typeOfSetAside=notice_data.get("typeOfSetAside"),
                    responseDeadLine=parse_date(notice_data.get("responseDeadLine")),
                    # naicsCode=notice_data.get("naicsCode"),
                    naicsCodes=notice_data.get("naicsCodes"),
                    classificationCode=notice_data.get("classificationCode"),
                    active=notice_data.get("active") == "Yes",
                    description=notice_data.get("description"),
                    organizationType=notice_data.get("organizationType"),
                    additionalInfoLink=notice_data.get("additionalInfoLink"),
                    uiLink=notice_data.get("uiLink"),
                    office_address=office_address,
                    place_of_performance=place_of_performance,
                )

                naics_code_value = notice_data.get("naicsCode")
                existing_naics_code = (
                    session.query(NaicsCodes).filter_by(naicsCode=naics_code_value).first()
                )

                if existing_naics_code:
                    # If exists, use the existing NaicsCodes instance
                    notice.naicsCode = existing_naics_code
                else:
                    # Otherwise, create a new NaicsCodes instance
                    new_naics_code = NaicsCodes(naicsCode=naics_code_value)
                    session.add(new_naics_code)
                    session.flush()
                    notice.naicsCode = new_naics_code

                poc_data_list = notice_data.get("pointOfContact", [])
                if poc_data_list:
                    for poc_data in poc_data_list:
                        poc = PointOfContact(
                            fax=poc_data.get("fax"),
                            type=poc_data.get("type"),
                            email=poc_data.get("email"),
                            phone=poc_data.get("phone"),
                            title=poc_data.get("title"),
                            fullName=poc_data.get("fullName"),
                            notice=notice,
                        )
                        session.add(poc)

                link_data_list = notice_data.get("links", [])
                if link_data_list:
                    for link_data in link_data_list:
                        link = Link(
                            rel=link_data.get("rel"), href=link_data.get("href"), notice=notice
                        )
                        session.add(link)

                resource_link_data = notice_data.get("resourceLinks", [])
                if resource_link_data:
                    for resource_link in resource_link_data:
                        res_link = ResourceLink(url=resource_link, notice=notice)
                        session.add(res_link)

                session.add(notice)
                notices_added += 1

            session.commit()
            logging.info(f"Added {notices_added} notices to database.")

    s3_response = get_opportunities_from_s3(bucket_name, file_name)
    commit_new_opportunities = commit_new_opportunities_to_postgres(s3_response)

    s3_response >> commit_new_opportunities


s3_opportunities_to_postgres_dag = s3_opportunities_to_postgres(bucket_name, file_name)
