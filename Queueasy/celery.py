from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Queueasy.settings')

app = Celery('Queueasy')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks(['main'])  # Ensure this is set to include your app
