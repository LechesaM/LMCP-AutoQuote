# ECS Commands for API/Worker/Beat

This repo builds a single image. In ECS you can run it as:
- API (default CMD): `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Worker: `celery -A app.celery_app.celery worker --loglevel=INFO -Q ingest,extract,pricing,pack,send,default`
- Beat: `celery -A app.celery_app.celery beat --loglevel=INFO`

In Terraform, you can run multiple ECS services (api/worker/beat) using the same image but different commands.
