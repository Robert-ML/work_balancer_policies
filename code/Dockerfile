# syntax=docker/dockerfile:1

FROM python:3.8

WORKDIR /app

RUN pip3 install aiohttp asyncio

COPY . .

CMD ["python3", "/app/load_generation.py"]
