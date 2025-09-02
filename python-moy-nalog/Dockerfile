# Simple runtime image for the CLI
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime deps
COPY pyproject.toml /app/
COPY moy_nalog /app/moy_nalog

RUN pip install --no-cache-dir .

# Default config dir mount for token persistence
VOLUME ["/root/.config/moy-nalog"]

ENTRYPOINT ["moy-nalog"]
CMD ["--help"]

