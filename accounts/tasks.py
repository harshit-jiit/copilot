# accounts/tasks.py
from celery import shared_task

@shared_task
def print_hello():
    print("✅ Hello from Celery task!")