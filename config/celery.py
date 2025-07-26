import os
import logging
from datetime import datetime
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# --- Logging setup ---
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'celery')
os.makedirs(LOG_DIR, exist_ok=True)

def setup_celery_logging(role):
    log_file = os.path.join(LOG_DIR, f"{role}_{datetime.today().date()}.log")

    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

# Define scheduled tasks
app.conf.beat_schedule = {
    'print-hello-every-10-seconds': {
        'task': 'accounts.tasks.print_hello',
        'schedule': 10.0,  # every 10 seconds
    },
}

app.conf.timezone = 'UTC'