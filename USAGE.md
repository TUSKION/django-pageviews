# Django PageViews Usage Guide

This guide will help you integrate Django PageViews into your project and start tracking page views with minimal effort.

## Basic Setup

### 1. Install the package

```bash
pip install django-pageviews
```

With async support (recommended for high-traffic sites):

```bash
pip install django-pageviews[async]
```

### 2. Add to INSTALLED_APPS

Add `django_pageviews` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'django_pageviews',
    # ...
]
```

### 3. Add the middleware

Add the PageView middleware to your `MIDDLEWARE` in `settings.py`:

```python
MIDDLEWARE = [
    # ...
    'django_pageviews.middleware.PageViewMiddleware',
    # ...
]
```

**Important**: Place the middleware after the Session middleware to enable session tracking.

### 4. Run migrations

```bash
python manage.py migrate django_pageviews
```

That's it! Page views will now be automatically tracked. The middleware will record information about each page view, including URL, view name, IP address, user agent, and session key.

## Tracking Model Objects

To track views for specific model objects, add the `PageViewMixin` to your model:

```python
from django.db import models
from django_pageviews.mixins import PageViewMixin

class Article(PageViewMixin, models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    # ...

    def get_absolute_url(self):
        # The middleware uses get_absolute_url to match URLs to objects
        return reverse('article_detail', kwargs={'slug': self.slug})
```

Now the middleware will automatically associate page views with the appropriate model objects when users view detail pages.

The `PageViewMixin` adds these properties and methods to your model:
- `view_count`: Get the total view count for the object
- `unique_view_count`: Get the count of unique visitors based on session keys
- `daily_views`: Get a breakdown of views by day
- `get_popular()`: Class method to get the most popular objects of this model type

## Tracking with Class-Based Views

If you're using Django's class-based views, you can track page views by adding the `PageViewMixin` to your view:

```python
from django.views.generic import View, ListView, DetailView
from django_pageviews.mixins import PageViewMixin

# Most basic usage - no additional methods needed
class ArticleDetailView(PageViewMixin, DetailView):
    model = Article
    template_name = 'article_detail.html'
    # The mixin automatically uses self.object - no extra code needed!

# For ListView - no methods needed for basic tracking
class ArticleListView(PageViewMixin, ListView):
    model = Article
    template_name = 'article_list.html'
    # By default, this will track the first object in the queryset
    
    # Only override this if you want to track something else:
    # def get_tracked_object(self):
    #     # For example, to track the category instead of the first article
    #     return Category.objects.get(slug=self.kwargs['category_slug'])
        
# For custom View - if using standard URL patterns, no methods needed
class ArticleView(PageViewMixin, View):
    model = Article  # Important! This enables automatic object resolution
    template_name = 'article.html'
    
    def get(self, request, *args, **kwargs):
        # Your view logic here
        article = Article.objects.get(slug=self.kwargs['slug'])
        return render(request, self.template_name, {'article': article})
    
    # You only need this if your view doesn't use standard URL kwargs (pk, id, slug)
    # def get_object(self):
    #     return Article.objects.get(slug=self.kwargs['slug'])
```

The `PageViewMixin` will track views for the object returned by `get_tracked_object()`. By default, it tries these strategies to find the object:

1. Use `self.object` if it exists (DetailView) - most common for DetailView
2. Call `self.get_object()` if available - only needed for custom views with non-standard object access
3. For ListView, use the first object in the queryset - happens automatically
4. If model is defined, try to get object from URL kwargs (pk, id, or slug) - happens automatically

**Important:** In most cases, you don't need to override any methods. The mixin will automatically find the right object to track. Only override `get_tracked_object()` if you want to track something other than what would be automatically detected.

### Note on Middleware Support

The middleware has been enhanced to work with all class-based views (View, ListView, DetailView). If you're already using the middleware, it will automatically attempt to find and track objects from your views without requiring the PageViewMixin.

With the middleware approach:
- You don't need to add the mixin to your views
- You don't need to add any additional methods
- Everything happens automatically based on the same object detection logic

The mixin is primarily useful when you want more control over which objects get tracked or when the middleware can't automatically determine the right object.

## Using Template Tags

Django PageViews includes several template tags to display view statistics in your templates.

First, load the template tags:

```html
{% load pageview_tags %}
```

### Display View Count

```html
<!-- Show view count for a specific object -->
<p>{% get_view_count article %} views</p>

<!-- Show view count for the current URL -->
<p>{% get_url_view_count %} views</p>

<!-- Show view count for a specific named view -->
<p>{% get_view_name_count 'article_detail' %} views</p>
```

### Display Popular Content

```html
<!-- Get popular articles -->
{% get_popular_objects 'Article' 'blog' limit=5 as popular_articles %}
{% for article, count in popular_articles %}
    <li>{{ article.title }} - {{ count }} views</li>
{% endfor %}

<!-- Get popular URLs -->
{% get_popular_urls limit=5 days=7 as popular_urls %}
{% for url, count in popular_urls %}
    <li><a href="{{ url }}">{{ url }}</a> - {{ count }} views</li>
{% endfor %}
```

### Get Daily View Data

```html
<!-- Get daily view counts for an object -->
{% get_daily_views article days=14 as daily_data %}
{% for date, count in daily_data.items %}
    <li>{{ date|date:"M d" }}: {{ count }} views</li>
{% endfor %}
```

## Configuration Options

Add these settings to your `settings.py` file (all are optional):

```python
# Throttle time in seconds to prevent duplicate counts from the same user
PAGEVIEW_THROTTLE_SECONDS = 20

# Number of views to process in one batch (for async processing)
PAGEVIEW_BATCH_SIZE = 100

# Maximum time in seconds to hold views in buffer
PAGEVIEW_BUFFER_TIMEOUT = 300

# Whether to use async processing (auto-detected by default)
PAGEVIEW_ASYNC_PROCESSING = True

# Patterns to identify bots (these requests will be ignored)
PAGEVIEW_BOT_PATTERNS = ['bot', 'crawl', 'spider', 'slurp', 'search', 'fetch', 'scan']

# Don't track views in the admin area
PAGEVIEW_EXCLUDE_ADMIN = True

# Don't track AJAX requests
PAGEVIEW_EXCLUDE_AJAX = True

# Paths to exclude from tracking (e.g. static files)
PAGEVIEW_EXCLUDE_PATHS = ['/static/', '/media/']

# IP addresses to exclude from tracking
PAGEVIEW_EXCLUDE_IP_ADDRESSES = ['127.0.0.1']
```

## Maintenance

### Clean Up Old Records

To keep your database size manageable, you can run the included management command to delete old page view records:

```bash
python manage.py clean_pageviews --days=90
```

This will delete all page view records older than 90 days.

To keep historical data while cleaning up:

```bash
python manage.py clean_pageviews --days=90 --keep-unique
```

This will keep at least one record per URL/object even if it's older than the specified days.

## Advanced Usage

### Manually Recording Page Views

In some cases, you might want to manually record a page view:

```python
from django_pageviews.models import PageView

# Record a view for a model object
PageView.increment_view_count(
    obj=article,
    ip_address=request.META.get('REMOTE_ADDR'),
    user_agent=request.META.get('HTTP_USER_AGENT'),
    session_key=request.session.session_key
)
```

This approach works well for custom tracking needs, but in most cases, using the `PageViewMixin` is simpler and more maintainable.

For function-based views:

```python
from django_pageviews.models import PageView

def article_view(request, slug):
    article = Article.objects.get(slug=slug)
    
    # Record the view
    PageView.increment_view_count(
        obj=article,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT'),
        session_key=request.session.session_key
    )
    
    return render(request, 'article.html', {'article': article})
```

### API Usage in Views

```python
from django_pageviews.models import PageView

def stats_view(request):
    # Get popular articles from the last 7 days
    from blog.models import Article
    popular_articles = PageView.get_popular_objects(Article, days=7)
    
    # Get popular URLs
    popular_urls = PageView.get_popular_urls(limit=10)
    
    return render(request, 'stats.html', {
        'popular_articles': popular_articles,
        'popular_urls': popular_urls,
    })
```

## For High-Traffic Sites

If you're using this on a high-traffic site, we recommend:

1. Install with async support: `pip install django-pageviews[async]`

2. See [ASYNC_USAGE.md](ASYNC_USAGE.md) for detailed setup instructions, including:
   - Setting up Celery and Redis
   - Running both Celery worker and beat processes
   - Advanced configuration options
   - Performance tuning recommendations
   - Troubleshooting common issues

This will allow page view recording to happen asynchronously without slowing down your site. The page views will be buffered in Redis and processed in batches by Celery workers.