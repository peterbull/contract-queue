FROM apache/airflow:2.8.2-python3.10

# Install additional dependencies for ECCODES
USER root

# Install and check for correct install with pthyon
RUN apt-get update && apt-get install -y python3-pip \
    libxml2-dev libxslt1-dev antiword unrtf poppler-utils tesseract-ocr \
    flac ffmpeg lame libmad0 libsox-fmt-mp3 sox libjpeg-dev swig libpulse-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install additional dependencies for project

USER airflow
WORKDIR /home/airflow

COPY airflow/requirements.txt . 
RUN pip install -r requirements.txt 