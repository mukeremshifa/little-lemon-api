"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # Application endpoints
    path("api/", include("LittleLemonAPI.urls")),

    # Djoser: registration + user management  ->  /api/users/, /api/users/me/
    path("api/", include("djoser.urls")),
    # Djoser token auth  ->  /api/token/login/, /api/token/logout/
    path("api/", include("djoser.urls.authtoken")),

    # DRF browsable-API login/logout
    path("api-auth/", include("rest_framework.urls")),
]
