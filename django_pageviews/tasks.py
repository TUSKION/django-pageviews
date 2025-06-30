from django.utils import timezone
from django.core.cache import cache
import time
import json

try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    # Define a simple decorator for fallback
    def shared_task(func):
        return func
    CELERY_AVAILABLE = False

try:
    from redis import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Import settings
from . import settings as app_settings

# Redis setup - only if available
redis_client = None
if REDIS_AVAILABLE and CELERY_AVAILABLE:
    try:
        from django.conf import settings
        redis_client = Redis.from_url(settings.CELERY_BROKER_URL)
    except (ImportError, AttributeError):
        pass

# Buffer key
PAGEVIEW_BUFFER_KEY = 'pageview_buffer'

@shared_task(name='django_pageviews.tasks.buffer_page_view')
def buffer_page_view(url, view_name=None, content_type_id=None, object_id=None, 
                    ip_address=None, user_agent=None, session_key=None):
    """Buffer the page view in Redis or process synchronously if Redis is unavailable"""
    try:
        view_data = {
            'url': url,
            'view_name': view_name,
            'content_type_id': content_type_id,
            'object_id': object_id,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'session_key': session_key,
            'timestamp': time.time()
        }
        
        # If Redis is available, buffer the view
        if redis_client:
            redis_client.lpush(PAGEVIEW_BUFFER_KEY, json.dumps(view_data))
            
            # If buffer reaches batch size, trigger processing
            batch_size = app_settings.get_setting('BATCH_SIZE')
            if redis_client.llen(PAGEVIEW_BUFFER_KEY) >= batch_size:
                process_pageview_buffer.delay()
                
            return True
        else:
            # Fall back to synchronous processing
            record_page_view(
                url=url,
                view_name=view_name,
                content_type_id=content_type_id,
                object_id=object_id,
                ip_address=ip_address,
                user_agent=user_agent,
                session_key=session_key
            )
            return True
            
    except Exception as e:
        print(f"Error buffering page view: {e}")
        # Try synchronous recording as fallback
        try:
            record_page_view(
                url=url,
                view_name=view_name,
                content_type_id=content_type_id,
                object_id=object_id,
                ip_address=ip_address,
                user_agent=user_agent,
                session_key=session_key
            )
        except:
            pass
        return False

@shared_task(name='django_pageviews.tasks.process_pageview_buffer')
def process_pageview_buffer():
    """Process buffered page views in batches"""
    if not redis_client:
        return
        
    try:
        # Import models here to avoid AppRegistryNotReady
        from django.contrib.contenttypes.models import ContentType
        from django_pageviews.models import PageView
        from django.utils import timezone
        
        # Get batch size from settings
        batch_size = app_settings.get_setting('BATCH_SIZE')
        
        # Get all views from buffer (up to batch size)
        views_to_process = []
        for _ in range(batch_size):
            view_data = redis_client.rpop(PAGEVIEW_BUFFER_KEY)
            if not view_data:
                break
            views_to_process.append(json.loads(view_data))
        
        # Bulk create page views
        page_views = []
        for view_data in views_to_process:
            content_type = None
            if view_data['content_type_id']:
                content_type = ContentType.objects.get(id=view_data['content_type_id'])
            
            page_views.append(
                PageView(
                    url=view_data['url'],
                    view_name=view_data['view_name'],
                    content_type=content_type,
                    object_id=view_data['object_id'],
                    ip_address=view_data['ip_address'],
                    user_agent=view_data['user_agent'],
                    session_key=view_data['session_key'],
                    timestamp=timezone.now()
                )
            )
        
        # Bulk create in database
        if page_views:
            PageView.objects.bulk_create(page_views)
            print(f"Processed {len(page_views)} page views")
            
    except Exception as e:
        print(f"Error processing page view buffer: {e}")
        import traceback
        traceback.print_exc()
        
@shared_task
def cleanup_old_buffer_data():
    """Clean up old data from Redis buffer"""
    if not redis_client:
        return
        
    try:
        buffer_timeout = app_settings.get_setting('BUFFER_TIMEOUT')
        cutoff_time = time.time() - buffer_timeout
        
        # Get all views from buffer
        buffer_length = redis_client.llen(PAGEVIEW_BUFFER_KEY)
        for i in range(buffer_length):
            view_data = redis_client.lindex(PAGEVIEW_BUFFER_KEY, i)
            if not view_data:
                continue
                
            view_data = json.loads(view_data)
            if view_data['timestamp'] < cutoff_time:
                # Process remaining views if they're old
                process_pageview_buffer.delay()
                break
                
    except Exception as e:
        print(f"Error cleaning up buffer: {e}")

@shared_task
def record_page_view(url, view_name=None, content_type_id=None, object_id=None, 
                     ip_address=None, user_agent=None, session_key=None):
    """
    Record a page view synchronously
    
    Important: All Django model imports must be inside this function
    to avoid AppRegistryNotReady errors.
    """
    # Import models inside the task function to avoid AppRegistryNotReady
    from django.contrib.contenttypes.models import ContentType
    from django_pageviews.models import PageView
    
    try:
        # Prepare content_type if provided
        content_type = None
        if content_type_id:
            content_type = ContentType.objects.get(id=content_type_id)
        
        # Create the page view
        page_view = PageView.objects.create(
            url=url,
            view_name=view_name,
            content_type=content_type,
            object_id=object_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key
        )
        
        # Update cache if object is tracked
        if content_type and object_id:
            cache_key = f'pageview_count_{content_type.id}_{object_id}'
            count = cache.get(cache_key)
            if count is not None:
                cache.set(cache_key, count + 1, 3600)
            
    except Exception as e:
        print(f"Error recording page view: {e}")
        import traceback
        traceback.print_exc()