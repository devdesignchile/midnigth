# app/accounts/urls.py
from django.urls import path
from .views import OwnerSignupView, GuestSignupView,login_view, ProfileEditView
from django.views.generic import TemplateView
from django.contrib.auth.views import LogoutView
from . import views



urlpatterns = [
    path("signup/", TemplateView.as_view(template_name="accounts/signup_choice.html"), name="signup-choice"),
    path("signup/company/", OwnerSignupView.as_view(), name="signup-company"),
    path("signup/guest/",   GuestSignupView.as_view(),  name="signup-guest"),
    path("login/", login_view, name="login"),
    path("logout/", LogoutView.as_view(next_page="home"), name="logout"),
    path("perfil/editar/", ProfileEditView.as_view(), name="profile_edit"),
    path("webhooks/mp/", views.mp_webhook, name="mp_webhook"),
    path("password/reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password/reset/done/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("password/reset/confirm/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("password/reset/complete/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # Cambiar contraseña (logueado)
    path("password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("password/change/done/", views.PasswordChangeDoneView.as_view(), name="password_change_done"),
]
