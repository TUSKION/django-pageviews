from django import template
from django.urls import resolve
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.utils import timezone

register = template.Library()

@register.filter
def format_number(value, precision=1):
    """
    Format a number to a more readable format (e.g., 1120 -> 1.1K)
    
    Usage:
    {{ view_count|format_number }}
    {{ view_count|format_number:2 }}  # 2 decimal places
    
    Args:
        value: The number to format
        precision: Number of decimal places (default: 1)
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return value
    
    if num < 1000:
        return str(int(num)) if num == int(num) else f"{num:.{precision}f}".rstrip('0').rstrip('.')
    
    # Define the suffixes and their corresponding values
    suffixes = [
        (1_000_000_000_000, 'T'),  # Trillion
        (1_000_000_000, 'B'),      # Billion
        (1_000_000, 'M'),          # Million
        (1_000, 'K'),              # Thousand
    ]
    
    for threshold, suffix in suffixes:
        if num >= threshold:
            formatted = num / threshold
            # Format with specified precision, then remove trailing zeros
            formatted_str = f"{formatted:.{precision}f}".rstrip('0').rstrip('.')
            return f"{formatted_str}{suffix}"
    
    return str(int(num)) if num == int(num) else f"{num:.{precision}f}".rstrip('0').rstrip('.')

@register.filter
def format_number_with_options(value, options="precision:1,min_threshold:1000"):
    """
    Format a number with more configuration options
    
    Usage:
    {{ view_count|format_number_with_options:"precision:2,min_threshold:10000" }}
    {{ view_count|format_number_with_options:"precision:0,min_threshold:1000,suffix_style:lower" }}
    
    Options:
        precision: Number of decimal places (default: 1)
        min_threshold: Minimum number before formatting kicks in (default: 1000)
        suffix_style: 'upper' (K,M,B) or 'lower' (k,m,b) (default: 'upper')
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return value
    
    # Parse options
    config = {
        'precision': 1,
        'min_threshold': 1000,
        'suffix_style': 'upper'
    }
    
    if options:
        for option in options.split(','):
            if ':' in option:
                key, val = option.strip().split(':', 1)
                key = key.strip()
                val = val.strip()
                
                if key == 'precision':
                    try:
                        config['precision'] = int(val)
                    except ValueError:
                        pass
                elif key == 'min_threshold':
                    try:
                        config['min_threshold'] = int(val)
                    except ValueError:
                        pass
                elif key == 'suffix_style':
                    if val.lower() in ['upper', 'lower']:
                        config['suffix_style'] = val.lower()
    
    # If below threshold, return as-is
    if num < config['min_threshold']:
        return str(int(num)) if num == int(num) else f"{num:.{config['precision']}f}".rstrip('0').rstrip('.')
    
    # Define the suffixes
    if config['suffix_style'] == 'lower':
        suffixes = [
            (1_000_000_000_000, 't'),
            (1_000_000_000, 'b'),
            (1_000_000, 'm'),
            (1_000, 'k'),
        ]
    else:
        suffixes = [
            (1_000_000_000_000, 'T'),
            (1_000_000_000, 'B'),
            (1_000_000, 'M'),
            (1_000, 'K'),
        ]
    
    for threshold, suffix in suffixes:
        if num >= threshold:
            formatted = num / threshold
            formatted_str = f"{formatted:.{config['precision']}f}".rstrip('0').rstrip('.')
            return f"{formatted_str}{suffix}"
    
    return str(int(num)) if num == int(num) else f"{num:.{config['precision']}f}".rstrip('0').rstrip('.')

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
def get_popular_objects(model_name, app_label=None, limit=5, days=None, select_related=None, prefetch_related=None):
    """
    Get the most viewed objects of a specific model type
    
    Usage:
    {% get_popular_objects 'Post' 'blog' limit=3 as popular_posts %}
    {% get_popular_objects 'Post' 'blog' limit=5 select_related='author' prefetch_related='tags,comments' as popular_posts %}
    {% for post, count in popular_posts %}
        <li>{{ post.title }} - {{ count }} views</li>
    {% endfor %}
    
    Args:
        model_name: The model class name (string)
        app_label: The app label (string, optional)
        limit: Max number of objects (int, optional)
        days: Only include views in the last N days (int, optional)
        select_related: Comma-separated related fields for select_related (string, optional)
        prefetch_related: Comma-separated related fields for prefetch_related (string, optional)
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
        # Parse select_related and prefetch_related if provided
        select_related_fields = [f.strip() for f in select_related.split(',')] if select_related else None
        prefetch_related_fields = [f.strip() for f in prefetch_related.split(',')] if prefetch_related else None
        return PageView.get_popular_objects(
            model_class,
            limit=limit,
            days=days,
            select_related=select_related_fields,
            prefetch_related=prefetch_related_fields
        )
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

@register.simple_tag
def get_view_counts_for_objects(objects):
    """
    Get a dict mapping object.pk to view count for a list of objects.
    Usage:
        {% get_view_counts_for_objects object_list as view_counts %}
        {{ view_counts|get_item:obj.pk }}
    """
    from django_pageviews.models import PageView
    return PageView.get_view_counts_for_objects(objects)

@register.filter
def get_item(dictionary, key):
    """
    Dictionary lookup by key for templates.
    Usage: {{ mydict|get_item:mykey }}
    """
    try:
        return dictionary.get(key, 0)
    except Exception:
        return 0