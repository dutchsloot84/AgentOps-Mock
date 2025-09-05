FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/mcp/claims_mcp.py app/mcp/claims_mcp.py
EXPOSE 9002
CMD ["uvicorn", "app.mcp.claims_mcp:app", "--host", "0.0.0.0", "--port", "9002"]
