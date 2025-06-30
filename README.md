# Django Page Views

A simple and efficient Django app for tracking page views on your website.

## Features

- Track page views for any model or view with a simple mixin
- Support for Django's View, ListView, and DetailView classes
- Automatic view tracking through middleware
- Advanced analytics: total views, unique views, time-based filtering
- Popular content tracking
- Support for Celery for async processing (optional)
- Template tags for easy integration in templates
- Bot filtering and throttling to prevent duplicate counts
- Management command to clean old records

## Installation

```bash
pip install django-pageviews
```

Or for async support:

```bash
pip install django-pageviews[async]
```

## Quick Start

1. Add "django_pageviews" to your INSTALLED_APPS setting:

```python
INSTALLED_APPS = [
    ...
    'django_pageviews',
]
```

2. Add the middleware to your settings:

```python
MIDDLEWARE = [
    ...
    'django_pageviews.middleware.PageViewMiddleware',
]
```

3. Run migrations to create the PageView model:

```bash
python manage.py migrate django_pageviews
```

4. Add the mixin to any model or view you want to track:

```python
from django.db import models
from django_pageviews.mixins import PageViewMixin

# For models:
class Article(PageViewMixin, models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    # ...

# For class-based views:
from django.views.generic import View, ListView, DetailView
from django_pageviews.mixins import PageViewMixin

# Most basic usage - no additional methods needed
class ArticleDetailView(PageViewMixin, DetailView):
    model = Article
    # The mixin automatically uses self.object - no extra code needed!

class ArticleListView(PageViewMixin, ListView):
    model = Article
    # By default, this will track the first object in the queryset
    
    # ONLY override this if you need custom tracking behavior:
    # def get_tracked_object(self):
    #     # For example, to track the category instead of the first item
    #     return Category.objects.get(slug=self.kwargs['category_slug'])

class ArticleView(PageViewMixin, View):
    model = Article  # Important! This enables automatic object resolution
    # The mixin will automatically find objects from URL kwargs (pk, id, slug)
```

5. Use the included template tags in your templates:

```html
{% load pageview_tags %}

<!-- Display view count for an object -->
<p>{% get_view_count article %} views</p>

<!-- Display popular objects -->
{% get_popular_objects 'Article' 'blog' limit=5 as popular_articles %}
{% for article, count in popular_articles %}
    <li>{{ article.title }} - {{ count }} views</li>
{% endfor %}
```

## Configuration

Add these settings to your settings.py file (all are optional with sensible defaults):

```python
# Throttle time in seconds to prevent duplicate counts from the same user
PAGEVIEW_THROTTLE_SECONDS = 20

# Number of views to process in one batch (for async processing)
PAGEVIEW_BATCH_SIZE = 100

# Maximum time in seconds to hold views in buffer
PAGEVIEW_BUFFER_TIMEOUT = 300
```

## Async Processing

For high-traffic sites, enable async processing with Celery and Redis:

1. Install with async support:
   ```bash
   pip install django-pageviews[async]
   ```

2. See [ASYNC_USAGE.md](ASYNC_USAGE.md) for detailed setup instructions, including:
   - Setting up Celery and Redis
   - Running both Celery worker and beat processes
   - Advanced configuration options
   - Performance tuning recommendations
   - Troubleshooting common issues

## Management Commands

Clean up old page view records:

```bash
python manage.py clean_pageviews --days=90
```

## License

MIT