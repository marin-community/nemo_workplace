FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

LABEL org.marin.taskcompendium.action-interface="workplace:v1" \
      org.marin.taskcompendium.seed-sha256="abcfd3d4727c66b6dfc145b59f720b819ac9de1b65df285cd30bc80bc10b3b8b" \
      org.marin.taskcompendium.provider-revision="1e668906d2e69a9e8ee9aaafc60050a4025d9688" \
      org.marin.taskcompendium.tools-sha256="16126f168b1cc4c3dde3eb90721f28acf2bdf47a2d887457fc4f38cd54470516"

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/opt/workplace/src
WORKDIR /opt/workplace
COPY requirements-container.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements-container.txt
COPY src/nemo_workplace src/nemo_workplace
COPY LICENSE NOTICE UPSTREAM_PROVENANCE.json ./
USER 65532:65532
CMD ["python", "-m", "nemo_workplace.server"]
