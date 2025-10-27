# app/accounts/urls.py
from django.urls import path
from .views import OwnerSignupView, GuestSignupView,login_view, ProfileEditView
from django.views.generic import TemplateView
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("signup/", TemplateView.as_view(template_name="accounts/signup_choice.html"), name="signup-choice"),
    path("signup/company/", OwnerSignupView.as_view(), name="signup-company"),
    path("signup/guest/",   GuestSignupView.as_view(),  name="signup-guest"),
    path("login/", login_view, name="login"),
    path("logout/", LogoutView.as_view(next_page="home"), name="logout"),
    path("perfil/editar/", ProfileEditView.as_view(), name="profile_edit"),
]
