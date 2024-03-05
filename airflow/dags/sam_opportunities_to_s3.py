import json
import logging
import os

import boto3
import pendulum
import requests
from airflow.decorators import dag, task

SAM_PUBLIC_API_KEY = os.environ.get("SAM_PUBLIC_API_KEY")
S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")

logging.basicConfig(level=logging.INFO)

start_date = pendulum.datetime(2024, 3, 1)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": start_date,
    "email": ["your-email@example.com"],
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": pendulum.duration(minutes=2),
}


@dag(
    catchup=False,
    start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
    schedule="@daily",
    tags=["produces", "dataset-scheduled"],
)
def ingest_opportunities_to_s3():

    # Using previous date until the time that new info is posted becomes known
    previous_date = pendulum.now("utc").subtract(days=1).strftime("%Y%m%d")
    formatted_request_date = pendulum.parse(previous_date, strict=False).format("MM/DD/YYYY")
    base_url = "https://api.sam.gov/opportunities/v2/search"
    bucket_name = "sam-gov-opportunities"

    api_params = {
        "api_key": SAM_PUBLIC_API_KEY,
        "postedFrom": formatted_request_date,
        "postedTo": formatted_request_date,
        "ptype": "o",
        "limit": 1000,
        "offset": 0,
    }

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

    @task()
    def opportunity_obj_to_s3(opportunities, bucket_name, previous_date):
        json_data = json.dumps(opportunities)
        bytes_data = json_data.encode("utf-8")
        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )
        bucket_name = bucket_name
        file_name = f"daily-opportunity-posts/{previous_date}.json"
        s3_client.put_object(Bucket=bucket_name, Key=file_name, Body=bytes_data)
        logging.info(f"Successfully wrote to S3 bucket {bucket_name} with key {file_name}")

    opportunities = get_new_opportunities(base_url, api_params)
    opportunity_obj_to_s3(opportunities, bucket_name, previous_date)


ingest_opportunities_to_s3()
