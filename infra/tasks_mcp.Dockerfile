FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/mcp/tasks_mcp.py app/mcp/tasks_mcp.py
COPY mocks/data/seed_tasks.json mocks/data/seed_tasks.json
EXPOSE 9001
ENV SEED_TASKS=mocks/data/seed_tasks.json
CMD ["uvicorn", "app.mcp.tasks_mcp:app", "--host", "0.0.0.0", "--port", "9001"]
