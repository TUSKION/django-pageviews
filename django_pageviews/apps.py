from django.apps import AppConfig


class PageviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'django_pageviews'
    verbose_name = 'Page Views'

    def ready(self):
        # Import tasks to ensure they're registered
        try:
            from . import tasks
        except ImportError:
            # If celery/tasks are not available, that's okay
            pass