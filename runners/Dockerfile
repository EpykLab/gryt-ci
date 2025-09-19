FROM ubuntu:latest
LABEL authors="gryt.dev"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    package2 \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["top", "-b"]