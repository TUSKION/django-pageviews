from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.conf import settings
from django.core.cache import cache

class PageView(models.Model):
    # Generic foreign key to any model (optional - can be null for non-object views)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # URL and view information
    url = models.CharField(max_length=2000)
    view_name = models.CharField(max_length=200, null=True, blank=True)
    
    # Request information
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['url']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['content_type', 'timestamp']),  # For date-filtered popular objects
            models.Index(fields=['view_name']),  # For view_name queries
        ]
        verbose_name = 'Page View'
        verbose_name_plural = 'Page Views'
    
    def __str__(self):
        if self.content_object:
            return f"View of {self.content_type.model} {self.object_id} at {self.timestamp}"
        return f"View of {self.url} at {self.timestamp}"
    
    @classmethod
    def get_view_count(cls, obj=None, url=None, view_name=None):
        """Get view count for an object, URL, or view name"""
        queryset = cls.objects.all()
        
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            queryset = queryset.filter(content_type=content_type, object_id=obj.id)
        
        if url:
            queryset = queryset.filter(url=url)
            
        if view_name:
            queryset = queryset.filter(view_name=view_name)
            
        return queryset.count()
    
    @classmethod
    def get_view_counts_for_objects(cls, objects):
        """
        Returns a dict mapping object.pk -> view count for all objects in the list.
        Optimized to avoid N+1 queries.
        """
        if not objects:
            return {}
        model = type(objects[0])
        content_type = ContentType.objects.get_for_model(model)
        object_ids = [obj.pk for obj in objects]
        counts = (
            cls.objects
            .filter(content_type=content_type, object_id__in=object_ids)
            .values('object_id')
            .annotate(count=Count('id'))
        )
        # Map object_id to count
        count_map = {item['object_id']: item['count'] for item in counts}
        # Ensure all objects are present, even if count is 0
        return {obj.pk: count_map.get(obj.pk, 0) for obj in objects}
    
    @classmethod
    def increment_view_count(cls, obj, ip_address=None, user_agent=None, session_key=None, request=None):
        """
        Record a page view, with caching/throttling to prevent duplicate/inflated counts.
        Throttles by object and user/session/IP for a configurable period (default 20s).
        """
        content_type = ContentType.objects.get_for_model(obj)
        throttle_seconds = getattr(settings, 'PAGEVIEW_THROTTLE_SECONDS', 20)

        # Build a cache key based on object and user/session/IP
        if request and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            user_key = f"user:{request.user.id}"
        elif session_key:
            user_key = f"session:{session_key}"
        elif ip_address:
            user_key = f"ip:{ip_address}"
        else:
            user_key = "anon"
        cache_key = f"pageview_throttle:{content_type.id}:{obj.id}:{user_key}"

        if cache.get(cache_key):
            return  # Already counted recently, skip

        # Create the page view record
        cls.objects.create(
            content_type=content_type,
            object_id=obj.id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key
        )
        cache.set(cache_key, True, throttle_seconds)

    @classmethod
    def get_views_by_period(cls, obj, days=None, start_date=None, end_date=None):
        """Get views for a specific time period"""
        content_type = ContentType.objects.get_for_model(obj)
        queryset = cls.objects.filter(
            content_type=content_type,
            object_id=obj.id
        )
        
        if days is not None:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(timestamp__gte=start_date)
        elif start_date and end_date:
            queryset = queryset.filter(timestamp__range=(start_date, end_date))
        
        return queryset.count()
    
    @classmethod
    def get_daily_views(cls, obj, days=30):
        """Get daily view counts for the last N days"""
        content_type = ContentType.objects.get_for_model(obj)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        # Get all views in the date range
        queryset = cls.objects.filter(
            content_type=content_type,
            object_id=obj.id,
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date
        )
        
        # Group by date and count
        from django.db.models.functions import TruncDate
        from django.db.models import Count
        
        daily_counts = queryset.annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Convert to a dictionary for easy access - more memory efficient
        result = {}
        for i in range(days):
            current_date = start_date + timedelta(days=i)
            result[current_date] = 0
        
        for item in daily_counts:
            result[item['date']] = item['count']
        
        return result
    
    @classmethod
    def get_popular_objects(cls, model_class, limit=5, days=None, select_related=None, prefetch_related=None):
        """
        Get the most viewed objects of a specific model type
        
        Args:
            model_class: The model class to get popular objects for
            limit: Maximum number of objects to return
            days: Optional, limit to views in the last X days
            select_related: Optional list/tuple of related fields to select_related
            prefetch_related: Optional list/tuple of related fields to prefetch_related
        
        Returns:
            A list of (object, view_count) tuples
        """
        content_type = ContentType.objects.get_for_model(model_class)
        queryset = cls.objects.filter(content_type=content_type)
        
        # Filter by date if specified
        if days:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(timestamp__gte=start_date)
        
        # Get object IDs and their view counts
        object_views = queryset.values('object_id').annotate(
            view_count=Count('id')
        ).order_by('-view_count')[:limit*2]  # Get more than needed in case some are invalid
        
        # Fetch all objects in one query to avoid N+1 problem
        object_ids = [item['object_id'] for item in object_views]
        
        object_qs = model_class.objects.filter(pk__in=object_ids)
        if hasattr(model_class, '_meta') and model_class._meta.get_field('slug'):
            object_qs = object_qs.exclude(slug__isnull=True).exclude(slug='')
        if select_related:
            object_qs = object_qs.select_related(*select_related)
        if prefetch_related:
            object_qs = object_qs.prefetch_related(*prefetch_related)
        
        objects_dict = {obj.pk: obj for obj in object_qs}
        
        # Build result with proper filtering
        result = []
        for item in object_views:
            obj = objects_dict.get(item['object_id'])
            if obj:
                result.append((obj, item['view_count']))
                if len(result) >= limit:
                    break
        
        return result
    
    @classmethod
    def get_popular_objects_raw(cls, model_class, limit=5, days=None, select_related=None, prefetch_related=None):
        """
        Get the most viewed objects of a specific model type without slug filtering
        
        Args:
            model_class: The model class to get popular objects for
            limit: Maximum number of objects to return
            days: Optional, limit to views in the last X days
            select_related: Optional list/tuple of related fields to select_related
            prefetch_related: Optional list/tuple of related fields to prefetch_related
        
        Returns:
            A list of (object, view_count) tuples
        """
        content_type = ContentType.objects.get_for_model(model_class)
        queryset = cls.objects.filter(content_type=content_type)
        
        # Filter by date if specified
        if days:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(timestamp__gte=start_date)
        
        # Get object IDs and their view counts
        object_views = queryset.values('object_id').annotate(
            view_count=Count('id')
        ).order_by('-view_count')[:limit]
        
        # Fetch all objects in one query to avoid N+1 problem
        object_ids = [item['object_id'] for item in object_views]
        object_qs = model_class.objects.filter(pk__in=object_ids)
        if select_related:
            object_qs = object_qs.select_related(*select_related)
        if prefetch_related:
            object_qs = object_qs.prefetch_related(*prefetch_related)
        objects_dict = {obj.pk: obj for obj in object_qs}
        
        # Build result
        result = []
        for item in object_views:
            obj = objects_dict.get(item['object_id'])
            if obj:
                result.append((obj, item['view_count']))
                if len(result) >= limit:
                    break
        
        return result
    
    @classmethod
    def get_popular_urls(cls, limit=5, days=None):
        """
        Get the most viewed URLs
        
        Args:
            limit: Maximum number of URLs to return
            days: Optional, limit to views in the last X days
        
        Returns:
            A list of (url, view_count) tuples
        """
        queryset = cls.objects.all()
        
        # Filter by date if specified
        if days:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(timestamp__gte=start_date)
        
        # Get URLs and their view counts
        url_views = queryset.values('url').annotate(
            view_count=Count('id')
        ).order_by('-view_count')[:limit]
        
        return [(item['url'], item['view_count']) for item in url_views]
    
    @classmethod
    def get_popular_view_names(cls, limit=5, days=None):
        """
        Get the most viewed named views
        
        Args:
            limit: Maximum number of view names to return
            days: Optional, limit to views in the last X days
        
        Returns:
            A list of (view_name, view_count) tuples
        """
        queryset = cls.objects.exclude(view_name__isnull=True).exclude(view_name='')
        
        # Filter by date if specified
        if days:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(timestamp__gte=start_date)
        
        # Get view names and their view counts
        view_name_views = queryset.values('view_name').annotate(
            view_count=Count('id')
        ).order_by('-view_count')[:limit]
        
        return [(item['view_name'], item['view_count']) for item in view_name_views]