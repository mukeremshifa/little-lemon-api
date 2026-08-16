"""Root URL configuration."""
from django.contrib import admin
from django.urls import include, path

from LittleLemonAPI import views

urlpatterns = [
    path("admin/", admin.site.urls),

    # HTML pages
    path("", views.index, name="index"),
    path("menu/", views.menu, name="menu"),
    path("book/", views.book, name="book"),

    # Browser auth: /accounts/login/, /accounts/logout/, /accounts/register/
    path("accounts/register/", views.RegisterView.as_view(), name="register"),
    path("accounts/", include("django.contrib.auth.urls")),

    # Application API endpoints
    path("api/", include("LittleLemonAPI.urls")),

    # Djoser: registration + user management  ->  /api/users/, /api/users/me/
    path("api/", include("djoser.urls")),
    # Djoser token auth  ->  /api/token/login/, /api/token/logout/
    #
    # Namespaced deliberately: Djoser names these routes "login" and "logout",
    # which would otherwise shadow django.contrib.auth's HTML views of the same
    # name and send {% url 'login' %} to the token API. Reverse them as
    # "djoser:login" / "djoser:logout"; the URL paths are unchanged.
    path("api/", include(("djoser.urls.authtoken", "djoser"), namespace="djoser")),

    # DRF browsable-API login/logout
    path("api-auth/", include("rest_framework.urls")),
]
