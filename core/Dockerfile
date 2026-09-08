FROM python:3.11-slim
WORKDIR /opt/cluster-bridge
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8765
CMD ["python3", "mcp_server.py"]
