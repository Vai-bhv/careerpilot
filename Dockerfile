FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HOME=/home/careerpilot
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends libreoffice-writer fonts-liberation curl && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 1000 careerpilot
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY frontend frontend
COPY migrations migrations
COPY .streamlit .streamlit
COPY demo demo
COPY alembic.ini pyproject.toml ./
RUN pip install --no-deps . && install -d -m 0700 -o careerpilot -g careerpilot private
USER careerpilot
CMD ["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
