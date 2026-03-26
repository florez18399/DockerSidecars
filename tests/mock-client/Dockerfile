FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir aiohttp

COPY traffic_generator.py .

CMD ["python", "traffic_generator.py"]
