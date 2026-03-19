"""
URL configuration for LexarAnon project.
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = 'LexarAnon — Админ-панель'
admin.site.site_title = 'LexarAnon Admin'
admin.site.index_title = 'Управление ботом'

urlpatterns = [
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
