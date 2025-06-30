from django.contrib import admin
from django.utils.html import format_html
from .models import PageView

@admin.register(PageView)
class PageViewAdmin(admin.ModelAdmin):
    list_display = ('view_details', 'timestamp', 'ip_address', 'get_user_agent_short')
    list_filter = ('timestamp', 'content_type')
    search_fields = ('url', 'view_name', 'ip_address', 'user_agent', 'session_key')
    date_hierarchy = 'timestamp'
    readonly_fields = ('content_type', 'object_id', 'url', 'view_name', 'ip_address', 'user_agent', 'session_key', 'timestamp')
    
    fieldsets = (
        (None, {
            'fields': ('url', 'view_name', 'timestamp'),
        }),
        ('Content Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',),
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'session_key'),
            'classes': ('collapse',),
        }),
    )
    
    def get_user_agent_short(self, obj):
        if not obj.user_agent:
            return "-"
        
        ua = obj.user_agent
        max_length = 30
        
        if len(ua) > max_length:
            return f"{ua[:max_length]}..."
        return ua
    
    get_user_agent_short.short_description = 'User Agent'
    
    def view_details(self, obj):
        if obj.content_object:
            content_type_name = obj.content_type.name.title()
            object_repr = str(obj.content_object)
            if len(object_repr) > 30:
                object_repr = object_repr[:27] + "..."
                
            return format_html(
                '<strong>{}</strong> <span class="small text-muted">({}: {})</span>',
                obj.url, content_type_name, object_repr
            )
        
        return obj.url
    
    view_details.short_description = 'View Details'
    
    def has_add_permission(self, request):
        # Prevent manual creation of page views
        return False