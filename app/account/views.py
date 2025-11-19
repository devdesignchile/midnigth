# ===== Standard library =====
import json
import datetime

# ===== Third-party =====
import mercadopago

# ===== Django =====
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, UpdateView

# ===== Local apps =====
from app.places.models import Commune

# arriba del archivo, junto a los imports
from django.contrib.auth import get_user_model
User = get_user_model()


from .forms import (
    OwnerSignupForm,
    GuestSignupForm,
    LoginForm,
    OwnerProfileUpdateForm,
    GuestProfileUpdateForm,
)
from .models import Profile, OwnerProfile, GuestProfile, Subscription


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



# SDK Mercado Pago
sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN)

# Tu ID de plan (desde el panel de Mercado Pago)
PLAN_ID = "ec21111b64994019978196a11936035c"


@csrf_exempt
def mp_webhook(request):
    """Webhook oficial de Mercado Pago para manejar suscripciones y pagos automáticos."""
    try:
        payload = json.loads(request.body or "{}")
    except Exception as e:
        print("❌ Error parsing webhook JSON:", e)
        return HttpResponse(status=400)

    event_type = payload.get("type") or payload.get("action") or payload.get("topic")
    resource_id = payload.get("data", {}).get("id") or payload.get("id")

    if not event_type or not resource_id:
        print("⚠️ Notificación sin tipo o ID:", payload)
        return HttpResponse(status=400)

    # 🟣 1) SUSCRIPCIONES (preapproval)
    if "preapproval" in event_type.lower():
        try:
            pre = sdk.preapproval().get(resource_id)["response"]
        except Exception as e:
            print("❌ Error obteniendo preapproval:", e)
            return HttpResponse(status=500)

        plan_id = pre.get("preapproval_plan_id")
        payer_email = (pre.get("payer_email") or "").lower().strip()
        status = (pre.get("status") or "").upper()  # AUTHORIZED, PAUSED, CANCELLED...

        print(f"📬 [Webhook preapproval] {payer_email} → {status}")

        # Validar plan y correo
        if plan_id != PLAN_ID or not payer_email:
            return HttpResponse(status=200)

        owner = OwnerProfile.objects.filter(company_email__iexact=payer_email).first()
        if not owner:
            print("⚠️ Owner no encontrado para:", payer_email)
            return HttpResponse(status=404)

        # Obtener o crear suscripción asociada al owner
        sub, _ = Subscription.objects.get_or_create(owner=owner)
        sub.mp_preapproval_id = pre.get("id")

        # Actualizar estado
        if status == "AUTHORIZED":
            base = max(timezone.now(), sub.current_period_end or timezone.now())
            sub.current_period_end = base + datetime.timedelta(days=31)
            sub.status = Subscription.ACTIVE
        elif status == "PAUSED":
            sub.status = Subscription.PAUSED
        elif status == "CANCELLED":
            sub.status = Subscription.CANCELLED

        sub.save()
        print(f"✅ Suscripción de {owner.venue_name} → {sub.status}")
        return HttpResponse(status=200)

    # 🟢 2) PAGOS PERIÓDICOS
    elif "payment" in event_type.lower():
        try:
            pay = sdk.payment().get(resource_id)["response"]
        except Exception as e:
            print("❌ Error obteniendo payment:", e)
            return HttpResponse(status=500)

        status = (pay.get("status") or "").lower()
        payer_email = (pay.get("payer", {}) or {}).get("email", "").lower().strip()
        print(f"📬 [Webhook payment] {payer_email} → {status}")

        if status != "approved" or not payer_email:
            return HttpResponse(status=200)

        owner = OwnerProfile.objects.filter(company_email__iexact=payer_email).first()
        if not owner:
            print("⚠️ Owner no encontrado para pago:", payer_email)
            return HttpResponse(status=404)

        sub, _ = Subscription.objects.get_or_create(owner=owner)
        base = max(timezone.now(), sub.current_period_end or timezone.now())
        sub.current_period_end = base + datetime.timedelta(days=31)
        sub.status = Subscription.ACTIVE
        sub.save(update_fields=["current_period_end", "status"])
        print(f"💰 Pago aprobado → {owner.venue_name} suscripción extendida.")
        return HttpResponse(status=200)

    # 🔵 3) Otros eventos (ignorados)
    print(f"ℹ️ Evento ignorado: {event_type}")
    return HttpResponse(status=200)


from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.contrib import messages


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/password_reset_email.txt"      # fallback texto plano (opcional)
    html_email_template_name = "accounts/password_reset_email.html"  # <<— NUEVO
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")

    def get_email_context(self, context):
        # Forzar marca si quieres
        context = super().get_email_context(context)
        context["site_name"] = context.get("site_name") or "Midnight"
        # Si quieres forzar dominio/protocolo:
        # context["domain"] = "midnight.cl"
        # context["protocol"] = "https"
        return context


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")

    def form_valid(self, form):
        messages.success(self.request, "¡Tu contraseña fue cambiada! Ahora puedes iniciar sesión.")
        return super().form_valid(form)


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"


class PasswordChangeView(LoginRequiredMixin, auth_views.PasswordChangeView):
    template_name = "accounts/password_change_form.html"
    success_url = reverse_lazy("password_change_done")

    def form_valid(self, form):
        messages.success(self.request, "Contraseña actualizada correctamente ✅")
        return super().form_valid(form)


class PasswordChangeDoneView(LoginRequiredMixin, auth_views.PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"

def terminos_view(request):
    context = {
        "version": "1.0",
        "last_update": "2025-01-01"
    }
    return render(request, "terminos.html", context)

def privacidad_view(request):
    context = {
        "version": "1.0",
        "last_update": "2025-01-01",
    }
    return render(request, "privacidad.html", context)