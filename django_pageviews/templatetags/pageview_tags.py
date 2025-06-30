from django import template
from django.urls import resolve
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone

register = template.Library()

@register.simple_tag
def get_view_count(obj):
    """Get the view count for an object"""
    from django_pageviews.models import PageView
    return PageView.get_view_count(obj=obj)

@register.simple_tag(takes_context=True)
def get_url_view_count(context, url=None):
    """Get the view count for the current URL or a specified URL"""
    if url is None:
        request = context['request']
        url = request.path
    
    from django_pageviews.models import PageView
    return PageView.get_view_count(url=url)

@register.simple_tag(takes_context=True)
def get_view_name_count(context, view_name=None):
    """Get the view count for the current view name or a specified view name"""
    if view_name is None:
        request = context['request']
        if hasattr(request, 'resolver_match'):
            view_name = request.resolver_match.view_name
    
    if view_name:
        from django_pageviews.models import PageView
        return PageView.get_view_count(view_name=view_name)
    return 0

@register.simple_tag
def get_popular_objects(model_name, app_label=None, limit=5, days=None):
    """
    Get the most viewed objects of a specific model type
    
    Usage:
    {% get_popular_objects 'Post' 'blog' limit=3 as popular_posts %}
    {% for post, count in popular_posts %}
        <li>{{ post.title }} - {{ count }} views</li>
    {% endfor %}
    """
    try:
        # Get the model class
        if app_label:
            model_class = apps.get_model(app_label, model_name)
        else:
            for app_config in apps.get_app_configs():
                try:
                    model_class = app_config.get_model(model_name)
                    break
                except LookupError:
                    continue
            else:
                return []
        
        from django_pageviews.models import PageView
        return PageView.get_popular_objects(model_class, limit=limit, days=days)
    
    except Exception as e:
        print(f"Error getting popular objects: {e}")
        return []

@register.simple_tag
def get_popular_urls(limit=5, days=None):
    """
    Get the most viewed URLs
    
    Usage:
    {% get_popular_urls limit=5 days=7 as popular_urls %}
    {% for url, count in popular_urls %}
        <li><a href="{{ url }}">{{ url }}</a> - {{ count }} views</li>
    {% endfor %}
    """
    from django_pageviews.models import PageView
    return PageView.get_popular_urls(limit=limit, days=days)

@register.simple_tag
def get_popular_view_names(limit=5, days=None):
    """
    Get the most viewed named views
    
    Usage:
    {% get_popular_view_names limit=5 as popular_views %}
    {% for view_name, count in popular_views %}
        <li>{{ view_name }} - {{ count }} views</li>
    {% endfor %}
    """
    from django_pageviews.models import PageView
    return PageView.get_popular_view_names(limit=limit, days=days)

@register.simple_tag
def get_daily_views(obj, days=30):
    """
    Get daily view counts for an object
    
    Usage:
    {% get_daily_views article days=14 as daily_data %}
    {% for date, count in daily_data.items %}
        <li>{{ date|date:"M d" }}: {{ count }} views</li>
    {% endfor %}
    """
    from django_pageviews.models import PageView
    return PageView.get_daily_views(obj, days=days)