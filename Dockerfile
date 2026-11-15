# Between: the Python server. Standard library only, plus the time-zone database.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Run as an ordinary user. uid 1000 matches the default "ubuntu" user on EC2,
# so the mounted data/ folder and .env (chmod 600) are readable without root.
RUN useradd --create-home --uid 1000 between

WORKDIR /app
COPY server.py task_rules.py gap_engine.py ./
COPY public ./public
COPY scripts ./scripts
# Files arrive with the Mac's permissions (often 600, owner-only), owned by root here, so the
# "between" user couldn't read server.py. Make code readable (not writable) by everyone.
# data/ stays private: it's created after this and owned by "between" only.
RUN chmod -R a+rX,go-w /app \
    && mkdir -p /app/data && chown between:between /app/data && chmod 700 /app/data

USER between
EXPOSE 8765

# Secrets come from /app/.env (mounted read-only at run time), never from the image.
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8765"]
