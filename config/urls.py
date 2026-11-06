from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns
import django.conf.urls.i18n as i18n_urls

urlpatterns = [
    path('i18n/', include(i18n_urls)),
    path('admin/', admin.site.urls),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('finance.urls')),
]
