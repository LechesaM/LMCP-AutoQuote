from kombu import Queue

# Declare dedicated queues
CELERY_QUEUES = (
    Queue("ingest"),
    Queue("extract"),
    Queue("pricing"),
    Queue("pack"),
    Queue("send"),
)

# Route tasks to queues
CELERY_ROUTES = {
    "app.tasks_pipeline.poll_etenders": {"queue": "ingest"},
    "app.tasks_pipeline.download_and_extract": {"queue": "extract"},
    "app.tasks_pipeline.run_pricing": {"queue": "pricing"},
    "app.tasks_pipeline.build_pack": {"queue": "pack"},
    "app.tasks_pipeline.gated_send": {"queue": "send"},
}
