FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY mocks/claims_api/main.py mocks/claims_api/main.py
EXPOSE 9000
CMD ["uvicorn", "mocks.claims_api.main:app", "--host", "0.0.0.0", "--port", "9000"]
