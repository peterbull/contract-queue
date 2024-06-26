# Airflow 2.8.2
import logging
import os
import re
import tempfile
from zipfile import BadZipfile

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
from sqlalchemy import and_, create_engine, or_, select, update, values
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
from typing_extensions import List, Optional

logging.basicConfig(level=logging.INFO)

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
    schedule="0 6 * * *",
    # schedule=None,
    is_paused_upon_creation=True,
)
def get_resource_link_contents():
    def get_file_name(res):
        """
        Extracts the file name from the 'Content-Disposition' header of the given response object.

        Args:
            res (Response): The response object containing the 'Content-Disposition' header.

        Returns:
            str: The extracted file name.

        Raises:
            ValueError: If 'Content-Disposition' header does not exist or does not contain 'filename='.
        """
        content_disposition = res.headers.get("Content-Disposition")
        if content_disposition and "filename=" in content_disposition:
            file_name = content_disposition.split("filename=")[1].strip('"')
            return file_name
        else:
            logging.error("Invalid 'Content-Disposition' header, returning empty string")
            return ""

    def get_file_size(res):
        """
        Get the file size from the response headers.

        Args:
            res (Response): The response object containing the headers.

        Returns:
            int: The file size in bytes.

        Raises:
            ValueError: If the 'Content-Length' header is missing or invalid.
        """
        content_length = res.headers.get("Content-Length")
        if content_length:
            file_size = res.headers.get("Content-Length")
            return int(file_size)
        else:
            logging.error("Invalid 'Content-Length' header, returning 0")
            return 0

    def num_tokens_in_corpus(input: str, encoding_name: str = "gpt-3.5-turbo") -> int:
        """
        Calculates the number of tokens in a given input string using the specified encoding.

        Args:
            input (str): The input string to calculate the number of tokens for.
            encoding_name (str, optional): The name of the encoding to use. Defaults to "gpt-3.5-turbo".

        Returns:
            int: The number of tokens in the input string.
        """
        encoding = tiktoken.encoding_for_model(encoding_name)
        num_tokens = len(encoding.encode(input))
        return num_tokens

    def get_doc_text(file_name, rm=True):
        """Textract a doc given its path

        Arguments:
            file_name {str} -- path to a doc
        """
        try:
            b_text = None
            try:
                b_text = textract.process(file_name, encoding="utf-8", errors="ignore")
            # ShellError with antiword occurs when an rtf is saved with a doc extension
            except textract.exceptions.ShellError as e:
                err_message = str(e)
                try:
                    if "antiword" in err_message and file_name.endswith(".doc"):
                        new_name = file_name.replace(".doc", ".rtf")
                        os.rename(file_name, new_name)
                        b_text = textract.process(new_name, encoding="utf-8", errors="ignore")
                except textract.exceptions.ShellError as ex:
                    logging.error(
                        "Error extracting text from a DOC file. Check that all dependencies of textract are installed.\n{}".format(
                            ex
                        )
                    )
            except textract.exceptions.MissingFileError as e:
                b_text = None
                logging.error(
                    f"Couldn't textract {file_name} since the file couldn't be found: {e}",
                    exc_info=True,
                )
            # This can be raised when a pdf is incorrectly saved as a .docx (GH183)
            except BadZipfile as e:
                if file_name.endswith(".docx"):
                    new_name = file_name.replace(".docx", ".pdf")
                    os.rename(file_name, new_name)
                    b_text = textract.process(
                        new_name, encoding="utf-8", method="pdftotext", errors="ignore"
                    )
                else:
                    b_text = None
                    logging.warning(
                        f"Exception occurred textracting {file_name}: {e}", exc_info=True
                    )
            # TypeError is raised when None is passed to str.decode()
            # This happens when textract can't extract text from scanned documents
            except TypeError:
                b_text = None
            except Exception as e:
                if re.match("^(.*) file; not supported", str(e)):
                    logging.warning(f"'{file_name}' is type {str(e)}")
                elif re.match("^The filename extension .zip is not yet supported", str(e)):
                    logging.warning(f"'{file_name}' is type zip and not supported by textract")
                else:
                    logging.warning(
                        f"Exception occurred textracting {file_name}: {e}", exc_info=True
                    )
                b_text = None
            text = b_text.decode("utf8", errors="ignore").strip() if b_text else ""
            if rm:
                try:
                    os.remove(file_name)
                except Exception as e:
                    logging.error(f"{e}Unable to remove {file_name}", exc_info=True)
                finally:
                    return text

        except Exception as e:
            logging.error(
                f"Error uncaught when trying to parse file {file_name}. Giving up and returning an empty string. {e}",
                exc_info=True,
            )
            text = "unparsable"

        return text

    @task()
    def get_unparsed_resource_links(batch_size: Optional[int] = None):
        """
        Retrieves a batch of unparsed resource links from the database.

        Args:
            batch_size (Optional[int]): The number of resource links to retrieve in a batch. Defaults to None.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing the retrieved resource links.
        """
        with SessionLocal() as session:
            subquery = select(ResourceLink.notice_id).distinct()
            stmt = (
                select(ResourceLink)
                .where(and_(ResourceLink.notice_id.in_(subquery), ResourceLink.text.is_(None)))
                .limit(batch_size)
            )
            results = session.execute(stmt).scalars().all()
            return [ResourceLinkBase.model_validate(result).dict() for result in results]

    @task()
    def parse_text_and_commit_to_db(resource_links: dict, max_byte_size: int = 3000000):
        """
        Parses the text content of resource links and commits the parsed text to the database.

        Args:
            resource_links (dict): A dictionary containing resource links.
            max_byte_size (int, optional): The maximum allowed file size in bytes. Defaults to 3000000.

        Returns:
            None
        """
        for resource_link in tqdm(resource_links):
            res = requests.get(resource_link.get("url"))
            file_name = get_file_name(res)
            file_size = get_file_size(res)
            logging.info(f"Name: {file_name}")
            logging.info(f"Size: {file_size}")
            if file_size > max_byte_size:
                logging.info("File size exceeds threshold and will be skipped")
                with SessionLocal() as session:
                    stmt = (
                        update(ResourceLink)
                        .where(ResourceLink.id == resource_link["id"])
                        .values(
                            text="unparsable",
                            file_name=file_name,
                            file_size=file_size,
                        )
                    )
                    session.execute(stmt)
                    session.commit()
                continue
            prefix, suffix = os.path.splitext(file_name)
            suffix = "." + suffix
            # Check for specific adobe decoding error
            adobe_err = "If this message is not eventually replaced by the proper contents of the document, your PDF"
            encoding_err = "ÿ"
            with tempfile.NamedTemporaryFile(prefix=prefix, suffix=suffix, delete=False) as tmp:
                tmp.write(res.content)
                tmp.flush()
                temp_path = tmp.name
                text = get_doc_text(temp_path, rm=True)
                with SessionLocal() as session:
                    if text and (adobe_err in text or encoding_err in text):
                        err_message = "adobe-error" if adobe_err in text else "encoding-error"
                        stmt = (
                            update(ResourceLink)
                            .where(ResourceLink.id == resource_link["id"])
                            .values(
                                text=err_message,
                                file_name=file_name,
                                file_size=file_size,
                            )
                        )
                        session.execute(stmt)
                        session.commit()
                    elif text:
                        # clean null characters before committing
                        text = text.replace("\x00", "\uFFFD")
                        file_tokens = num_tokens_in_corpus(text)
                        stmt = (
                            update(ResourceLink)
                            .where(ResourceLink.id == resource_link["id"])
                            .values(
                                text=text,
                                file_name=file_name,
                                file_size=file_size,
                                file_tokens=file_tokens,
                            )
                        )
                        session.execute(stmt)
                        session.commit()
                    else:
                        stmt = (
                            update(ResourceLink)
                            .where(ResourceLink.id == resource_link["id"])
                            .values(
                                text="unparsable",
                                file_name=file_name,
                                file_size=file_size,
                            )
                        )
                        session.execute(stmt)
                        session.commit()

    new_resource_links = get_unparsed_resource_links()
    parse_text_and_commit_to_db(new_resource_links)


get_resource_link_contents_dag = get_resource_link_contents()
