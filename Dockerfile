FROM python:3.14-slim-bookworm


ARG CONTEXT=production
ENV CONTEXT=${CONTEXT}
ARG VERSION=develop
ENV VERSION=${VERSION}


RUN bash -euo pipefail <<EOF
apt update
apt install --yes --no-install-recommends \
    ca-certificates \
    netcat-traditional \
    entr 
update-ca-certificates
rm -rf /var/cache/apt/archives /var/lib/apt/lists/*
EOF

WORKDIR /app
COPY requirements.txt /app/
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV ENTR_INOTIFY_WORKAROUND=1

RUN bash -euo pipefail <<EOF
mkdir -p static src coverage htmlcov
pip install --no-cache-dir --root-user-action ignore -r requirements.txt
EOF

COPY entrypoint pyproject.toml .coveragerc /app/
COPY ./src /app/src

ENTRYPOINT ["/app/entrypoint"]
EXPOSE 8000
CMD ["start"]

