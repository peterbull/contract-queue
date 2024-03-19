# Airflow 2.8.2
import logging
import os

import boto3
import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from airflow import DAG

logging.basicConfig(level=logging.INFO)

# This is for working in development, on Saturday or Sundary there are little to no posted Notices
# Set this offest to match a weekday to ensure a decent size dataset to work with
# i.e., today is Sunday, so set the offset to `2` to match Notices from Friday.
day_offset = int(os.environ.get("DAY_OFFSET"))

# Database Backup
db_date = pendulum.now().strftime("%y%m%d")
file_name = f"db_backup_{db_date}.sql"
db_file_path = f"~/{file_name}"

# S3
S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")
bucket_name = "sam-postgres-backups"
aws_prior_date = pendulum.now().subtract(days=day_offset).strftime("%y%m%d")

# Dates
start_date = pendulum.datetime(2024, 3, 1)
prior_date = pendulum.now().subtract(days=day_offset).strftime("%Y-%m-%d")

# Postgres
pg_password = os.environ.get("POSTGRES_PASSWORD")
pg_user = os.environ.get("POSTGRES_USER")
pg_host = os.environ.get("POSTGRES_SERVER")
pg_port = os.environ.get("POSTGRES_PORT")
pg_database = os.environ.get("POSTGRES_DB")

with DAG(
    dag_id="backup_db_to_s3",
    catchup=False,
    start_date=start_date,
    schedule_interval=None,
    is_paused_upon_creation=True,
) as dag:
    backup_database = BashOperator(
        task_id="backup_database",
        bash_command=(
            f"PGPASSWORD='{pg_password}' "
            f"pg_dump -U {pg_user} "
            f"-h {pg_host} "
            f"-p {pg_port} "
            f"-d {pg_database} "
            f"> {db_file_path}"
        ),
        env={"PGPASSWORD": pg_password},
    )

    remove_dumped_database = BashOperator(
        task_id="remove_dumped_database",
        bash_command=f"rm {db_file_path}",
    )

    @task()
    def opportunity_obj_to_s3():
        s3_client = boto3.client(
            "s3",
            region_name=S3_REGION_NAME,
            aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
        )

        expanded_file_path = os.path.expanduser(db_file_path)
        with open(expanded_file_path, "rb") as f:
            bytes_data = f.read()

        s3_client.put_object(Bucket=bucket_name, Key=file_name, Body=bytes_data)
        logging.info(f"Successfully wrote to S3 bucket {bucket_name} with key {file_name}")

    upload_to_s3 = opportunity_obj_to_s3()
    backup_database >> upload_to_s3 >> remove_dumped_database
