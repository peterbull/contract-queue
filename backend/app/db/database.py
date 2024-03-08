import json
import os

import boto3
from app.core.config import get_app_settings
from app.models.models import Base
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from sqlalchemy import create_engine, event, exists, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

S3_AWS_ACCESS_KEY_ID = os.environ.get("S3_AWS_ACCESS_KEY_ID")
S3_AWS_SECRET_ACCESS_KEY = os.environ.get("S3_AWS_SECRET_ACCESS_KEY")
S3_REGION_NAME = os.environ.get("S3_REGION_NAME")

DATABASE_URL = get_app_settings().database_conn_string

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

s3_client = boto3.client(
    "s3",
    region_name=S3_REGION_NAME,
    aws_access_key_id=S3_AWS_ACCESS_KEY_ID,
    aws_secret_access_key=S3_AWS_SECRET_ACCESS_KEY,
)


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
