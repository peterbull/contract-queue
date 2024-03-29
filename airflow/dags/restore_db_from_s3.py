# Airflow 2.8.2
import logging
import os

import boto3
import pendulum
from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

from airflow import DAG

logging.basicConfig(level=logging.INFO)


def restore_db_from_s3():
    """
    DAG to restore a PostgreSQL database from an S3 backup file.

    This is currently a roundabout way to handle this and will need to be refactored. It sidesteps
    some blocking issues that occur due to spinning up the airflow side of the database on build in
    docker.

    This DAG performs the following steps:
    1. Downloads the database backup file from an S3 bucket.
    2. Creates a temporary database.
    3. Restores the backup file to the temporary database.
    4. Drops specified tables from the target database.
    5. Copies data from the temporary database to the target database.
    6. Drops the temporary database.
    7. Removes the downloaded backup file.

    The DAG is scheduled to run manually and is paused upon creation.

    Environment variables required:
    - DAY_OFFSET: Offset to match a weekday for a decent size dataset.
    - S3_AWS_ACCESS_KEY_ID: AWS access key ID for S3.
    - S3_AWS_SECRET_ACCESS_KEY: AWS secret access key for S3.
    - S3_REGION_NAME: AWS region name for S3.
    - POSTGRES_PASSWORD: Password for the PostgreSQL database.
    - POSTGRES_USER: Username for the PostgreSQL database.
    - POSTGRES_SERVER: Hostname or IP address of the PostgreSQL server.
    - POSTGRES_PORT: Port number of the PostgreSQL server.
    - POSTGRES_DB: Name of the target PostgreSQL database.

    Args:
        None

    Returns:
        None
    """
    # This is for working in development, on Saturday or Sunday there are little to no posted Notices
    # Set this offset to match a weekday to ensure a decent size dataset to work with
    # i.e., today is Sunday, so set the offset to `2` to match Notices from Friday.
    day_offset = int(os.environ.get("DAY_OFFSET"))

    # Database Backup
    db_date = "240325"
    file_name = f"db_backup_{db_date}.sql"
    db_file_path = f"~/{file_name}"

    # S3
    S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
    S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
    S3_REGION_NAME = os.environ.get("S3_REGION_NAME")
    bucket_name = "sam-postgres-backups"

    # Dates
    start_date = pendulum.datetime(2024, 3, 1)

    # Postgres
    pg_password = os.environ.get("POSTGRES_PASSWORD")
    pg_user = os.environ.get("POSTGRES_USER")
    pg_host = os.environ.get("POSTGRES_SERVER")
    pg_port = os.environ.get("POSTGRES_PORT")
    pg_database = os.environ.get("POSTGRES_DB")

    with DAG(
        dag_id="restore_db_from_s3",
        catchup=False,
        start_date=start_date,
        schedule_interval=None,
        is_paused_upon_creation=True,
    ) as dag:

        create_temp_database = BashOperator(
            task_id="create_temp_database",
            bash_command=(
                f"PGPASSWORD='{pg_password}' "
                f"psql -U {pg_user} "
                f"-h {pg_host} "
                f"-p {pg_port} "
                f"-c 'CREATE DATABASE temp_db;'"
            ),
            env={"PGPASSWORD": pg_password},
        )

        restore_to_temp_database = BashOperator(
            task_id="restore_to_temp_database",
            bash_command=(
                f"PGPASSWORD='{pg_password}' "
                f"psql -U {pg_user} "
                f"-h {pg_host} "
                f"-p {pg_port} "
                f"-d temp_db "
                f"-f {db_file_path}"
            ),
            env={"PGPASSWORD": pg_password},
        )

        tables_to_copy = [
            "naics_codes",
            "notices",
            "office_addresses",
            "places_of_performance",
            "points_of_contact",
            "resource_links",
            "summary_chunks",
            "mean_embeddings",
        ]

        drop_tables = BashOperator(
            task_id="drop_tables",
            bash_command=(
                f"PGPASSWORD='{pg_password}' "
                f"psql -U {pg_user} "
                f"-h {pg_host} "
                f"-p {pg_port} "
                f"-d {pg_database} "
                f"-c '"
                + "; ".join(f"DROP TABLE IF EXISTS {table} CASCADE" for table in tables_to_copy)
                + "'"
            ),
            env={"PGPASSWORD": pg_password},
        )

        copy_data_to_target_database = BashOperator(
            task_id="copy_data_to_target_database",
            bash_command=(
                f"PGPASSWORD='{pg_password}' "
                f"pg_dump -U {pg_user} "
                f"-h {pg_host} "
                f"-p {pg_port} "
                f"-d temp_db " + " ".join(f"-t {table}" for table in tables_to_copy) + " | "
                f"psql -U {pg_user} "
                f"-h {pg_host} "
                f"-p {pg_port} "
                f"-d {pg_database}"
            ),
            env={"PGPASSWORD": pg_password},
        )

        drop_temp_database = BashOperator(
            task_id="drop_temp_database",
            bash_command=(
                f"PGPASSWORD='{pg_password}' "
                f"psql -U {pg_user} "
                f"-h {pg_host} "
                f"-p {pg_port} "
                f"-c 'DROP DATABASE temp_db;'"
            ),
            env={"PGPASSWORD": pg_password},
        )

        remove_dumped_database = BashOperator(
            task_id="remove_dumped_database",
            bash_command=f"rm {db_file_path}",
        )

        @task()
        def get_backup_db_from_s3():
            s3_client = boto3.client(
                "s3",
                region_name=S3_REGION_NAME,
                aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
                aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
            )

            db_file_path_expanded = os.path.expanduser(db_file_path)
            s3_client.download_file(
                Bucket=bucket_name, Key=file_name, Filename=db_file_path_expanded
            )
            logging.info(
                f"Successfully downloaded {file_name} from S3 bucket {bucket_name} to {db_file_path_expanded}"
            )

        get_s3_backup = get_backup_db_from_s3()
        (
            get_s3_backup
            >> create_temp_database
            >> restore_to_temp_database
            >> drop_tables
            >> copy_data_to_target_database
            >> drop_temp_database
            >> remove_dumped_database
        )


restore_db_from_s3()
