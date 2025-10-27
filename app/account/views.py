# app/accounts/views.py
from django.urls import reverse_lazy
from django.views.generic import FormView
from .forms import OwnerSignupForm, GuestSignupForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Q
from .forms import LoginForm
from app.places.models import Commune
from django.db import transaction, IntegrityError

class OwnerSignupView(FormView):
    template_name = "accounts/signup_owner.html"
    form_class = OwnerSignupForm
    success_url = reverse_lazy("home")  # o "login" si quieres

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save()  # crea User, Profile y OwnerProfile
        except IntegrityError:
            form.add_error(None, "No pudimos crear la cuenta. Intenta nuevamente.")
            return self.form_invalid(form)
        messages.success(self.request, "¡Cuenta creada! Ya puedes iniciar sesión.")
        return super().form_valid(form)

    def form_invalid(self, form):
        # Útil para debug en consola
        print("OwnerSignupForm errors:", form.errors.as_data())
        return super().form_invalid(form)

class GuestSignupView(FormView):
    template_name = "accounts/signup_guest.html"
    form_class = GuestSignupForm
    success_url = reverse_lazy("home")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["city"].queryset = Commune.objects.all().order_by("name")
        return form

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Cuenta creada.")
        return super().form_valid(form)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")  # cambia por tu destino

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        password = form.cleaned_data["password"]

        # Buscar usuario por email (case-insensitive)
        try:
            user = User.objects.get(Q(email__iexact=email))
        except User.DoesNotExist:
            user = None

        if user:
            user = authenticate(request, username=user.username, password=password)
        if user is not None:
            login(request, user)
            # Manejo "Recordarme"
            if not form.cleaned_data.get("remember"):
                request.session.set_expiry(0)  # cerrar al cerrar navegador
            # Redirección segura
            next_url = request.GET.get("next") or "home"
            return redirect(next_url)
        else:
            messages.error(request, "Correo o contraseña inválidos.")

    return render(request, "accounts/login.html", {"form": form})


# app/accounts/views.py (añade esto)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from .models import Profile, OwnerProfile, GuestProfile
from .forms import OwnerProfileUpdateForm, GuestProfileUpdateForm

class ProfileEditView(LoginRequiredMixin, UpdateView):
    template_name = "accounts/profile_edit.html"  # ver más abajo
    success_url = reverse_lazy("profile_edit")    # vuelve a la misma página

    def dispatch(self, request, *args, **kwargs):
        # Asegura que el usuario tenga Profile y su subperfil
        if not hasattr(request.user, "profile"):
            messages.error(request, "Tu perfil aún no está creado.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    # Elegimos el objeto según rol
    def get_object(self, queryset=None):
        profile: Profile = self.request.user.profile
        if profile.is_owner:
            # si aún no existe (raro), lo creamos
            obj, _ = OwnerProfile.objects.get_or_create(profile=profile)
            return obj
        # guest
        obj, _ = GuestProfile.objects.get_or_create(
            profile=profile,
            defaults={"first_name": self.request.user.first_name or "",
                      "last_name": self.request.user.last_name or "",
                      "city": ""}
        )
        return obj

    # Elegimos el form según rol
    def get_form_class(self):
        profile: Profile = self.request.user.profile
        return OwnerProfileUpdateForm if profile.is_owner else GuestProfileUpdateForm

    # Context extra para pintar UI distinta por rol y sugerencias de ciudades
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        prof: Profile = self.request.user.profile
        ctx["is_owner"] = prof.is_owner
        ctx["is_guest"] = prof.is_guest

        # Sugerencias de ciudades en <datalist> (si tienes Commune)
        try:
            from app.places.models import Commune
            ctx["cities"] = list(Commune.objects.order_by("name").values_list("name", flat=True)[:300])
        except Exception:
            ctx["cities"] = []
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Perfil actualizado ✨")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Revisa los campos en rojo.")
        return super().form_invalid(form)
