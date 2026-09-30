FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/workplace/src
WORKDIR /opt/workplace
COPY requirements-container.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-container.txt
COPY src/nemo_workplace src/nemo_workplace
COPY LICENSE NOTICE UPSTREAM_PROVENANCE.json ./
USER 65532:65532
CMD ["python", "-m", "nemo_workplace.server"]
