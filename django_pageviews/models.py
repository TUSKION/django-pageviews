from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
from django.db.models import Count

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
    def increment_view_count(cls, obj, ip_address=None, user_agent=None, session_key=None):
        """Record a page view and update the cache"""
        content_type = ContentType.objects.get_for_model(obj)
        
        # Create the page view record
        cls.objects.create(
            content_type=content_type,
            object_id=obj.id,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key
        )
        
        # Update the cache
        cache_key = f'pageview_count_{content_type.id}_{obj.id}'
        count = cache.get(cache_key)
        if count is not None:
            cache.set(cache_key, count + 1, 3600)

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
        
        # Convert to a dictionary for easy access
        result = {(start_date + timedelta(days=i)): 0 for i in range(days)}
        for item in daily_counts:
            result[item['date']] = item['count']
        
        return result
    
    @classmethod
    def get_popular_objects(cls, model_class, limit=5, days=None):
        """
        Get the most viewed objects of a specific model type
        
        Args:
            model_class: The model class to get popular objects for
            limit: Maximum number of objects to return
            days: Optional, limit to views in the last X days
        
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
        
        # Fetch the actual objects
        result = []
        for item in object_views:
            try:
                obj = model_class.objects.get(pk=item['object_id'])
                
                # Check if the object has a slug and it's not empty
                if hasattr(obj, 'slug') and obj.slug:
                    result.append((obj, item['view_count']))
                
                # Stop once we have enough valid objects
                if len(result) >= limit:
                    break
                
            except model_class.DoesNotExist:
                continue
                
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