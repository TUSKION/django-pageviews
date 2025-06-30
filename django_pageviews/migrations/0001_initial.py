from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.CreateModel(
            name='PageView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('url', models.CharField(max_length=2000)),
                ('view_name', models.CharField(blank=True, max_length=200, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.TextField(blank=True, null=True)),
                ('session_key', models.CharField(blank=True, max_length=40, null=True)),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name': 'Page View',
                'verbose_name_plural': 'Page Views',
            },
        ),
        migrations.AddIndex(
            model_name='pageview',
            index=models.Index(fields=['content_type', 'object_id'], name='django_page_content_4f111b_idx'),
        ),
        migrations.AddIndex(
            model_name='pageview',
            index=models.Index(fields=['url'], name='django_page_url_3d5c2e_idx'),
        ),
        migrations.AddIndex(
            model_name='pageview',
            index=models.Index(fields=['timestamp'], name='django_page_timesta_a2ab55_idx'),
        ),
    ]