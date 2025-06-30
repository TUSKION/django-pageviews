from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django_pageviews.models import PageView

class Command(BaseCommand):
    help = 'Clean old page view records'
    
    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=90,
                            help='Delete records older than this many days')
        parser.add_argument('--keep-unique', action='store_true', 
                            help='Keep at least one record per URL/object for historical data')
    
    def handle(self, *args, **options):
        days = options['days']
        keep_unique = options['keep_unique']
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(f'Finding page views older than {days} days...')
        
        query = PageView.objects.filter(timestamp__lt=cutoff_date)
        
        if keep_unique:
            self.stdout.write('Keeping one record per URL/object for historical data...')
            # For each URL, keep the most recent view
            kept_urls = set()
            kept_objects = set()
            
            # Find URLs to keep
            for url in PageView.objects.values_list('url', flat=True).distinct():
                most_recent = PageView.objects.filter(
                    url=url, 
                    timestamp__lt=cutoff_date
                ).order_by('-timestamp').first()
                
                if most_recent:
                    kept_urls.add(most_recent.id)
            
            # Find objects to keep
            for ct_id, obj_id in PageView.objects.exclude(
                content_type__isnull=True
            ).exclude(
                object_id__isnull=True
            ).values_list('content_type_id', 'object_id').distinct():
                most_recent = PageView.objects.filter(
                    content_type_id=ct_id,
                    object_id=obj_id,
                    timestamp__lt=cutoff_date
                ).order_by('-timestamp').first()
                
                if most_recent:
                    kept_objects.add(most_recent.id)
            
            # Combine the IDs to keep
            keep_ids = kept_urls.union(kept_objects)
            query = query.exclude(id__in=keep_ids)
        
        # Get count before deletion
        count = query.count()
        
        # Delete old records
        query.delete()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully deleted {count} old page view records')
        )