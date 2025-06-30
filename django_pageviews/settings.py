from django.conf import settings

# Default settings for the pageviews app
DEFAULTS = {
    'THROTTLE_SECONDS': 20,
    'BATCH_SIZE': 100,
    'BUFFER_TIMEOUT': 300,
    'ASYNC_PROCESSING': False,  # By default, use synchronous processing
    'BOT_PATTERNS': ['bot', 'crawl', 'spider', 'slurp', 'search', 'fetch', 'scan'],
    'EXCLUDE_ADMIN': True,  # Don't track views in the admin area
    'EXCLUDE_AJAX': True,   # Don't track AJAX requests
    'EXCLUDE_PATHS': ['/static/', '/media/'],  # Don't track static/media paths
    'EXCLUDE_IP_ADDRESSES': [],  # Optional list of IP addresses to exclude
}

def get_setting(name):
    """
    Get a setting or return the default
    
    Settings will be read from the Django settings with the 'PAGEVIEW_' prefix.
    For example, PAGEVIEW_THROTTLE_SECONDS.
    """
    setting_name = f'PAGEVIEW_{name}'
    return getattr(settings, setting_name, DEFAULTS.get(name))

# Detect if Celery is available
def has_celery():
    try:
        import celery
        return True
    except ImportError:
        return False

# Detect if Redis is available
def has_redis():
    try:
        import redis
        return True
    except ImportError:
        return False

# Automatically set async processing based on availability
# only if the user hasn't explicitly set it
if 'ASYNC_PROCESSING' not in dir(settings):
    DEFAULTS['ASYNC_PROCESSING'] = has_celery() and has_redis()