from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.urls import resolve
from django.core.cache import cache
from . import settings as app_settings

class PageViewMiddleware(MiddlewareMixin):
    """
    Middleware to automatically track page views.

    This middleware captures information about page views and records them
    either synchronously or asynchronously depending on configuration.
    """
    def process_response(self, request, response):
        # Only track successful page views
        if response.status_code == 200 and request.method == 'GET':
            try:
                # Check if we should skip this view
                if not self._should_track_view(request):
                    return response

                # Check if we should throttle this view
                if not self._should_record_view(request):
                    return response

                # Get basic request information
                url = request.path
                view_name = None
                content_type_id = None
                object_id = None

                # Get resolver match information if available
                if hasattr(request, 'resolver_match') and request.resolver_match:
                    view_name = request.resolver_match.view_name

                    # Try to extract object information
                    view_func = request.resolver_match.func
                    kwargs = request.resolver_match.kwargs

                    # Try different strategies to get the object
                    obj = self._get_object_from_view(request, view_func, kwargs)

                    if obj:
                        # Import ContentType inside the method to avoid AppRegistryNotReady
                        from django.contrib.contenttypes.models import ContentType
                        content_type = ContentType.objects.get_for_model(obj)
                        content_type_id = content_type.id
                        object_id = obj.id

                # Get IP address
                ip_address = self.get_client_ip(request)

                # Get user agent
                user_agent = request.META.get('HTTP_USER_AGENT', '')

                # Get session key (if available)
                session_key = None
                if hasattr(request, 'session') and hasattr(request.session, 'session_key'):
                    session_key = request.session.session_key
                    # Ensure we have a session key
                    if not session_key:
                        request.session.save()
                        session_key = request.session.session_key

                # Use async processing if configured and available
                if app_settings.get_setting('ASYNC_PROCESSING'):
                    # Import here to avoid AppRegistryNotReady
                    try:
                        from .tasks import buffer_page_view
                        buffer_page_view.delay(
                            url=url,
                            view_name=view_name,
                            content_type_id=content_type_id,
                            object_id=object_id,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            session_key=session_key
                        )
                    except (ImportError, AttributeError):
                        # Fall back to synchronous processing if tasks aren't available
                        self._record_view_sync(
                            url=url,
                            view_name=view_name,
                            content_type_id=content_type_id,
                            object_id=object_id,
                            ip_address=ip_address,
                            user_agent=user_agent,
                            session_key=session_key
                        )
                else:
                    # Use synchronous processing
                    self._record_view_sync(
                        url=url,
                        view_name=view_name,
                        content_type_id=content_type_id,
                        object_id=object_id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        session_key=session_key
                    )

            except Exception as e:
                print(f"Error in page view middleware: {e}")
                import traceback
                traceback.print_exc()

        return response

    def _should_track_view(self, request):
        """
        Determine if this view should be tracked at all.
        Returns True if the view should be tracked, False otherwise.
        """
        # Skip admin views if configured
        if app_settings.get_setting('EXCLUDE_ADMIN'):
            if request.path.startswith('/admin/'):
                return False

        # Skip AJAX requests if configured
        if app_settings.get_setting('EXCLUDE_AJAX'):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return False

        # Skip excluded paths
        excluded_paths = app_settings.get_setting('EXCLUDE_PATHS')
        for path in excluded_paths:
            if path in request.path:
                return False

        # Skip excluded IP addresses
        excluded_ips = app_settings.get_setting('EXCLUDE_IP_ADDRESSES')
        if self.get_client_ip(request) in excluded_ips:
            return False

        return True

    def _should_record_view(self, request):
        """
        Determine if we should record this view based on throttling rules.
        Returns True if the view should be recorded, False otherwise.
        """
        # Skip bots
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        bot_patterns = app_settings.get_setting('BOT_PATTERNS')

        if any(pattern in user_agent for pattern in bot_patterns):
            return False

        # Get throttle time from settings
        throttle_seconds = app_settings.get_setting('THROTTLE_SECONDS')

        # Get the current URL
        url = request.path

        # Create a cache key based on session or IP
        if request.user.is_authenticated:
            # For authenticated users, use their user ID
            user_key = f"user:{request.user.id}"
        elif hasattr(request, 'session') and request.session.session_key:
            # For users with a session, use their session key
            user_key = f"session:{request.session.session_key}"
        else:
            # Fall back to IP address
            user_key = f"ip:{self.get_client_ip(request)}"

        # Create a combined cache key
        cache_key = f"pageview_throttle:{user_key}:{url}"

        # Check if this combination has been viewed recently
        if cache.get(cache_key):
            return False

        # Set a cache entry for this combination
        cache.set(cache_key, True, throttle_seconds)

        return True

    def _get_object_from_view(self, request, view_func, kwargs):
        """Try different strategies to get the object from the view"""
        obj = None

        # Only proceed if it's a class-based view
        if hasattr(view_func, 'view_class'):
            view_class = view_func.view_class

            try:
                # Create an instance of the view
                view_instance = view_class()
                view_instance.request = request
                view_instance.kwargs = kwargs
                view_instance.args = []

                # First check if view has get_tracked_object method (from PageViewMixin)
                if hasattr(view_class, 'get_tracked_object'):
                    try:
                        # Set up basic context for the view instance
                        if hasattr(view_class, 'get_queryset'):
                            view_instance.object_list = view_instance.get_queryset()
                        
                        # Call get_tracked_object and return its result directly
                        # This will respect None returns from get_tracked_object
                        return view_instance.get_tracked_object()
                    except Exception as e:
                        print(f"Error calling get_tracked_object: {e}")

                # Check if view has get_object method (DetailView)
                if hasattr(view_class, 'get_object'):
                    try:
                        view_instance.object = None  # Initialize object attribute
                        obj = view_instance.get_object()
                        if obj:
                            return obj
                    except Exception as e:
                        print(f"Error getting object from DetailView: {e}")

                # Check if it's a ListView
                if hasattr(view_class, 'get_queryset'):
                    try:
                        # Set up view for get_queryset
                        if not hasattr(view_instance, 'object_list'):
                            view_instance.object_list = None

                        # Get the queryset and return the first object if available
                        queryset = view_instance.get_queryset()
                        if queryset and hasattr(queryset, 'exists') and queryset.exists():
                            obj = queryset.first()
                            if obj:
                                return obj
                    except Exception as e:
                        print(f"Error getting object from ListView: {e}")

                # Check if it's a regular View with model attribute
                if hasattr(view_class, 'model'):
                    try:
                        # Try to get the object using kwargs
                        model = view_class.model
                        # Look for common primary key fields in kwargs
                        for pk_field in ('pk', 'id', 'slug'):
                            if pk_field in kwargs:
                                lookup = {pk_field: kwargs[pk_field]}
                                try:
                                    obj = model.objects.get(**lookup)
                                    if obj:
                                        return obj
                                except model.DoesNotExist:
                                    continue
                    except Exception as e:
                        print(f"Error getting object from View with model: {e}")

                # Check if view has an object attribute already
                if hasattr(view_instance, 'object') and view_instance.object:
                    return view_instance.object

            except Exception as e:
                print(f"Error creating view instance: {e}")

        return obj

    def _record_view_sync(self, url, view_name=None, content_type_id=None, object_id=None,
                         ip_address=None, user_agent=None, session_key=None):
        """Record a page view synchronously"""
        # Import here to avoid circular imports
        from django_pageviews.models import PageView
        from django.contrib.contenttypes.models import ContentType

        # Prepare content_type if provided
        content_type = None
        if content_type_id:
            content_type = ContentType.objects.get(id=content_type_id)

        # Create the page view
        PageView.objects.create(
            url=url,
            view_name=view_name,
            content_type=content_type,
            object_id=object_id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key
        )

    def get_client_ip(self, request):
        """Get the client IP address (supports both IPv4 and IPv6, Cloudflare, proxies)"""
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        real_ip = request.META.get('HTTP_X_REAL_IP')
        remote_addr = request.META.get('REMOTE_ADDR', '')

        if cf_ip:
            ip = cf_ip
        elif x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        elif real_ip:
            ip = real_ip
        else:
            ip = remote_addr

        # Handle IPv6 addresses that might be enclosed in brackets
        if ip.startswith('[') and ip.endswith(']'):
            ip = ip[1:-1]

        # If we have multiple addresses with port info (happens in some proxy setups)
        if ip and ':' in ip:
            # Check if it's IPv6 (more than 2 colons) or IPv4 with port
            if ip.count(':') > 1:
                # It's IPv6 - leave it as is
                pass
            else:
                # It's likely IPv4 with port - remove port part
                ip = ip.split(':')[0]

        return ip
