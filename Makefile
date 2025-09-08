PROJECT_ID?=$(shell gcloud config get-value project)
REGION?=us-central1

.PHONY: deps run-agent run-tasks run-claims run-claims-mock upsert deploy-mock deploy-tasks deploy-claims deploy-agent urls clean

deps:
pip install -r requirements.txt

run-agent:
uvicorn app.main:app --host 0.0.0.0 --port 8080

run-tasks:
uvicorn app.mcp.tasks_mcp:app --host 0.0.0.0 --port 9001

run-claims-mock:
uvicorn mocks.claims_api.main:app --host 0.0.0.0 --port 9000

run-claims:
CLAIMS_BASE=$$(gcloud run services describe claims-mock --region $(REGION) --format 'value(status.url)') \
uvicorn app.mcp.claims_mcp:app --host 0.0.0.0 --port 9002

upsert:
PROJECT_ID=$(PROJECT_ID) LOCATION=$(REGION) python -m app.retriever.upsert_vector

deploy-mock:
gcloud builds submit --tag gcr.io/$(PROJECT_ID)/claims-mock .
gcloud run deploy claims-mock --image gcr.io/$(PROJECT_ID)/claims-mock --allow-unauthenticated --region $(REGION) --port 9000 --command uvicorn --args mocks.claims_api.main:app,--host,0.0.0.0,--port,9000

deploy-tasks:
gcloud builds submit --tag gcr.io/$(PROJECT_ID)/tasks-mcp -f infra/tasks_mcp.Dockerfile .
gcloud run deploy tasks-mcp --image gcr.io/$(PROJECT_ID)/tasks-mcp --allow-unauthenticated --region $(REGION) --port 9001

deploy-claims:
CLAIMS_BASE=$$(gcloud run services describe claims-mock --region $(REGION) --format 'value(status.url)') \
gcloud builds submit --tag gcr.io/$(PROJECT_ID)/claims-mcp -f infra/claims_mcp.Dockerfile . && \
gcloud run deploy claims-mcp --image gcr.io/$(PROJECT_ID)/claims-mcp --allow-unauthenticated --region $(REGION) --port 9002 --set-env-vars CLAIMS_BASE=$$CLAIMS_BASE

deploy-agent:
TASKS_MCP_BASE=$$(gcloud run services describe tasks-mcp --region $(REGION) --format 'value(status.url)'); \
CLAIMS_MCP_BASE=$$(gcloud run services describe claims-mcp --region $(REGION) --format 'value(status.url)'); \
gcloud builds submit --tag gcr.io/$(PROJECT_ID)/agentops-mock -f infra/agent.Dockerfile . && \
gcloud run deploy agentops-mock --image gcr.io/$(PROJECT_ID)/agentops-mock --allow-unauthenticated --region $(REGION) --port 8080 \
  --set-env-vars PROJECT_ID=$(PROJECT_ID),LOCATION=$(REGION),INDEX_DISPLAY_NAME=agentops-mock-index,ENDPOINT_DISPLAY_NAME=agentops-mock-endpoint,TASKS_MCP_BASE=$$TASKS_MCP_BASE,CLAIMS_MCP_BASE=$$CLAIMS_MCP_BASE

urls:
@echo Agent: $$(gcloud run services describe agentops-mock --region $(REGION) --format 'value(status.url)')
@echo Tasks MCP: $$(gcloud run services describe tasks-mcp --region $(REGION) --format 'value(status.url)')
@echo Claims MCP: $$(gcloud run services describe claims-mcp --region $(REGION) --format 'value(status.url)')
@echo Claims Mock: $$(gcloud run services describe claims-mock --region $(REGION) --format 'value(status.url)')

clean:
-gcloud run services delete agentops-mock --region $(REGION) -q
-gcloud run services delete tasks-mcp --region $(REGION) -q
-gcloud run services delete claims-mcp --region $(REGION) -q
-gcloud run services delete claims-mock --region $(REGION) -q
