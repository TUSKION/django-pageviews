from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
import inspect


class PageViewMixin:
    """
    A mixin that adds page view tracking functionality to models and views.
    
    For models:
    
    class Article(PageViewMixin, models.Model):
        title = models.CharField(max_length=200)
        # ...
    
    This adds view_count and unique_view_count properties to your model instances,
    as well as a get_popular() class method.
    
    For views:
    
    class ArticleView(PageViewMixin, View):
        model = Article
        # ...
    
    class ArticleListView(PageViewMixin, ListView):
        model = Article
        # ...
        
    You can override get_tracked_object() to customize which object's views are tracked.
    """
    @classmethod
    def __init_subclass__(cls, **kwargs):
        """
        This method is called when a class that inherits from PageViewMixin is created.
        We use it to determine if the mixin is being used with a model or a view.
        """
        super().__init_subclass__(**kwargs)
        
        # Check if this is a view (has dispatch method)
        if hasattr(cls, 'dispatch'):
            # Monkey patch the dispatch method
            original_dispatch = cls.dispatch
            
            def patched_dispatch(self, request, *args, **kwargs):
                response = original_dispatch(self, request, *args, **kwargs)
                
                # Only track successful GET requests
                if request.method == 'GET' and response.status_code == 200:
                    try:
                        # Get the object to track
                        obj = self.get_tracked_object()
                        
                        if obj:
                            # Import here to avoid circular imports
                            from django_pageviews.models import PageView
                            
                            # Get IP address
                            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                            if x_forwarded_for:
                                ip_address = x_forwarded_for.split(',')[0]
                            else:
                                ip_address = request.META.get('REMOTE_ADDR')
                            
                            # Get user agent
                            user_agent = request.META.get('HTTP_USER_AGENT', '')
                            
                            # Get session key
                            session_key = None
                            if hasattr(request, 'session') and hasattr(request.session, 'session_key'):
                                session_key = request.session.session_key
                                if not session_key:
                                    request.session.save()
                                    session_key = request.session.session_key
                            
                            # Record the view
                            PageView.increment_view_count(
                                obj=obj,
                                ip_address=ip_address, 
                                user_agent=user_agent,
                                session_key=session_key
                            )
                    except Exception as e:
                        # Don't let errors in tracking disrupt the response
                        import traceback
                        traceback.print_exc()
                
                return response
                
            # Replace the dispatch method with our patched version
            cls.dispatch = patched_dispatch
    
    def get_tracked_object(self):
        """
        Get the object to track views for.
        
        This method tries different approaches:
        1. Use self.object if it exists (DetailView)
        2. Use self.get_object() if available
        3. For ListView, use the first object in the queryset
        4. If model is defined, try to get object from kwargs
        
        Override this method to customize tracking behavior.
        """
        # First try to use self.object if it exists (DetailView already populated it)
        if hasattr(self, 'object') and self.object:
            return self.object
            
        # Next try to use get_object() if available
        if hasattr(self, 'get_object'):
            try:
                return self.get_object()
            except Exception:
                pass
                
        # For ListView, try to get the first object from queryset
        if hasattr(self, 'get_queryset'):
            try:
                queryset = self.get_queryset()
                if queryset and hasattr(queryset, 'exists') and queryset.exists():
                    return queryset.first()
            except Exception:
                pass
                
        # If model is defined, try to get object from kwargs
        if hasattr(self, 'model') and hasattr(self, 'kwargs'):
            try:
                # Look for common primary key fields in kwargs
                for pk_field in ('pk', 'id', 'slug'):
                    if pk_field in self.kwargs:
                        lookup = {pk_field: self.kwargs[pk_field]}
                        try:
                            return self.model.objects.get(**lookup)
                        except self.model.DoesNotExist:
                            continue
            except Exception:
                pass
                
        return None
        

    @property
    def view_count(self):
        """Get the view count for this object"""
        from django_pageviews.models import PageView
        return PageView.get_view_count(obj=self)

    @property
    def unique_view_count(self):
        """Get the unique view count based on session keys or IP addresses"""
        from django_pageviews.models import PageView
        from django.contrib.contenttypes.models import ContentType
        
        content_type = ContentType.objects.get_for_model(self)
        
        # Count unique session keys (excluding empty ones)
        session_count = PageView.objects.filter(
            content_type=content_type,
            object_id=self.id
        ).exclude(
            session_key__isnull=True
        ).exclude(
            session_key=''
        ).values('session_key').distinct().count()
        
        return session_count 

    @classmethod
    def get_popular(cls, limit=5, days=None):
        """
        Get the most popular objects of this model type
        
        Args:
            limit: Maximum number of objects to return
            days: Optional, limit to views in the last X days
            
        Returns:
            A list of (object, view_count) tuples
        """
        # Only run this method if we're in a model
        if not (hasattr(cls, 'objects') and hasattr(cls, '_meta')):
            return []
            
        from django_pageviews.models import PageView
        return PageView.get_popular_objects(cls, limit=limit, days=days)
    
    @property
    def daily_views(self, days=30):
        """
        Get daily view counts for the last N days
        
        Args:
            days: Number of days to include
            
        Returns:
            A dictionary mapping dates to view counts
        """
        from django_pageviews.models import PageView
        return PageView.get_daily_views(self, days=days)