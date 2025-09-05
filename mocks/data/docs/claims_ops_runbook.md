# Claims Ops Runbook (Mock)
- FNOL payload must include external_ref, claimant_name, incident_ts.
- Soft limit: 5 attachments per request; batch if more.
- Retry policy: 3 attempts, exponential backoff.
- Status API: /status returns ok flag and timestamp.
- Claim lookup: /claims/{id} returns status and metadata.
