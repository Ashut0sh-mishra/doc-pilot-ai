FROM python:3.12-slim
WORKDIR /service
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 poppler-utils && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/api-requirements.txt
COPY ocr_worker/requirements.txt /tmp/ocr-requirements.txt
RUN pip install --no-cache-dir -r /tmp/api-requirements.txt -r /tmp/ocr-requirements.txt
COPY app ./app
COPY ocr_worker ./ocr_worker
CMD ["python", "-m", "ocr_worker.run", "--watch"]
