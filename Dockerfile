FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
# Optional: include tests to allow wheels to resolve extras if needed.
COPY tests ./tests

RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir .


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . .

RUN useradd -m namel3ss
USER namel3ss

# Default to an interactive shell; override with `docker run ... n3 run ...` or similar.
CMD ["/bin/bash"]
