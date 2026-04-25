FROM python:3.11-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y gcc

# install uv
RUN pip install uv

# copy project
COPY . .

# install deps
RUN uv sync

# expose API port
EXPOSE 8000

# default command (API)
CMD ["uv", "run", "uvicorn", "agentic_trader.api.app:app", "--host", "0.0.0.0", "--port", "8000"]