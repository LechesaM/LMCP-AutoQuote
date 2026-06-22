# Workers

`lmcp-core/workers/` will own future worker process definitions and queue-bound execution modules.

Responsibility:

- background task execution boundaries
- worker bootstrapping
- queue ownership by domain
- task registration aligned with the platform structure

Current status:

- placeholder structure only
- the current official worker entrypoint remains `app.celery_app.celery_app`

