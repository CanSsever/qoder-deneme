"""
Worker main entry point for background processing.
"""
from apps.worker.tasks import celery_app

if __name__ == '__main__':
    celery_app.start()