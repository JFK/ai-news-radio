FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir $(python -c "\
import tomllib; \
cfg=tomllib.load(open('pyproject.toml','rb')); \
deps=cfg['project']['dependencies']+cfg['project'].get('optional-dependencies',{}).get('dev',[]); \
print(' '.join(deps))")

COPY . .

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
