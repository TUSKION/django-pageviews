# Django PageViews - Asynchronous Processing Guide

This guide explains how to set up and use the asynchronous processing capabilities of the Django PageViews app using Celery and Redis.

## Why Use Async Processing?

For high-traffic websites, asynchronous processing offers several benefits:

- **Improved Performance**: Page view tracking doesn't slow down your website's response time
- **Better Scalability**: Handle spikes in traffic more efficiently
- **Reduced Database Load**: Page views are buffered and processed in batches
- **Improved Reliability**: Failed tracking attempts can be retried automatically

## Requirements

To use async processing with Django PageViews, you'll need:

1. Celery (4.0+)
2. Redis (recommended) or another message broker
3. django-pageviews installed with async support

## Installation

```bash
pip install django-pageviews[async]
```

This will install the required dependencies for async processing including Celery.

## Setting Up Celery

### 1. Create a celery.py file

Create a `celery.py` file in your project directory (next to your `settings.py`):

```python
import os
from celery import Celery

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yourproject.settings')

# Create the Celery app
app = Celery('yourproject')

# Load settings from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Optional: Define Celery beat schedule for periodic tasks
app.conf.beat_schedule = {
    'process-pageview-buffer': {
        'task': 'django_pageviews.tasks.process_pageview_buffer',
        'schedule': 60.0,  # Run every minute
    },
    'cleanup-old-buffer-data': {
        'task': 'django_pageviews.tasks.cleanup_old_buffer_data',
        'schedule': 300.0,  # Run every 5 minutes
    },
}
```

### 2. Update Your Project's __init__.py

Update your project's `__init__.py` file (same directory as your `settings.py`):

```python
# This ensures the Celery app is loaded when Django starts
from .celery import app as celery_app

__all__ = ('celery_app',)
```

### 3. Configure Settings

Add the following to your `settings.py` file:

```python
# Celery Settings
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Django PageViews Async Settings
PAGEVIEW_ASYNC_PROCESSING = True
PAGEVIEW_BATCH_SIZE = 100  # Number of views to process in one batch
PAGEVIEW_BUFFER_TIMEOUT = 300  # Max time in seconds to hold views in buffer
```

## Running Celery

Celery requires two processes to be running:

### 1. Celery Worker

The worker processes tasks from the queue:

```bash
# Run in the same directory as manage.py
celery -A yourproject worker -l info
```

For production, you should use a process manager like Supervisor or systemd to ensure Celery workers stay running.

### 2. Celery Beat

Celery Beat schedules periodic tasks:

```bash
# Run in the same directory as manage.py
celery -A yourproject beat -l info
```

Beat is essential for django-pageviews as it periodically:
- Processes the pageview buffer (task: `process_pageview_buffer`)
- Cleans up old buffer data (task: `cleanup_old_buffer_data`)

## Advanced Configuration

### Custom Task Routing

If you have multiple queues:

```python
# In settings.py
CELERY_TASK_ROUTES = {
    'django_pageviews.tasks.*': {'queue': 'pageviews'},
}
```

### Worker Concurrency

For high-traffic sites, increase worker concurrency:

```bash
celery -A yourproject worker -l info --concurrency=8
```

### Memory Management

To prevent memory leaks:

```bash
celery -A yourproject worker -l info --max-tasks-per-child=1000
```

## Monitoring Celery

Consider using Flower, a web-based tool for monitoring Celery:

```bash
pip install flower
celery -A yourproject flower
```

Then access the dashboard at http://localhost:5555

## Troubleshooting

### Common Issues

1. **Tasks not being processed**
   - Check if both worker and beat are running
   - Verify Redis is running: `redis-cli ping`
   - Check Celery logs for errors

2. **Memory usage growing**
   - Use `--max-tasks-per-child` option when starting workers
   - Ensure your Redis buffer isn't growing indefinitely

3. **Database connection errors**
   - Use Django's database connection management:
     ```python
     # In celery.py
     @app.task(bind=True)
     def debug_task(self, **kwargs):
         from django.db import connection
         connection.close()
     ```

### Disabling Async Processing

If you need to temporarily disable async processing:

```python
# In settings.py
PAGEVIEW_ASYNC_PROCESSING = False
```

## Performance Tuning

For very high traffic sites:

1. **Increase batch size**
   ```python
   PAGEVIEW_BATCH_SIZE = 500
   ```

2. **Decrease process frequency**
   ```python
   # In celery.py
   app.conf.beat_schedule = {
       'process-pageview-buffer': {
           'task': 'django_pageviews.tasks.process_pageview_buffer',
           'schedule': 120.0,  # Run every 2 minutes
       },
   }
   ```

3. **Separate queues for page view processing**
   ```python
   # In settings.py
   CELERY_TASK_ROUTES = {
       'django_pageviews.tasks.buffer_page_view': {'queue': 'pageviews-buffer'},
       'django_pageviews.tasks.process_pageview_buffer': {'queue': 'pageviews-process'},
   }
   ```

4. **Run dedicated workers**
   ```bash
   celery -A yourproject worker -l info -Q pageviews-buffer
   celery -A yourproject worker -l info -Q pageviews-process
   ```
