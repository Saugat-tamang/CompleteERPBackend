from django.urls import path

from .views import SSOLoginView


urlpatterns = [
    path("sso/login/", SSOLoginView.as_view(), name="sso-login"),
]