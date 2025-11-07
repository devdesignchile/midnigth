# app/accounts/models.py
from django.conf import settings
# app/accounts/models.py
from datetime import date
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
User = settings.AUTH_USER_MODEL  # django.contrib.auth.models.User

class Profile(models.Model):
    ROLE_CHOICES = (("owner", "Dueño de local"), ("guest", "Asistente"))
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"

    @property
    def is_owner(self): return self.role == "owner"
    @property
    def is_guest(self): return self.role == "guest"


from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.conf import settings

User = settings.AUTH_USER_MODEL  # django.contrib.auth.models.User


class Profile(models.Model):
    ROLE_CHOICES = (("owner", "Dueño de local"), ("guest", "Asistente"))
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"

    @property
    def is_owner(self): return self.role == "owner"
    @property
    def is_guest(self): return self.role == "guest"


class OwnerProfile(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="owner")
    venue_name = models.CharField("Nombre del local", max_length=120)
    admin_name = models.CharField("Nombre administrador", max_length=120)
    rut_comercio = models.CharField("RUT comercio", max_length=14)
    company_email = models.EmailField("Correo corporativo", unique=True)
    company_domain = models.CharField("Dominio comercial", max_length=120, unique=True)

    owner_verified = models.BooleanField(default=False)
    is_subscribed_admin = models.BooleanField(
        default=False,
        verbose_name="Suscrito (Admin)",
        help_text="Marcar manualmente para activar la suscripción del dueño."
    )
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Owner<{self.profile.user}> {self.venue_name}"

    # 🔁 Sincroniza automáticamente el estado de suscripción
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # sincroniza Subscription del usuario
        from .models import Subscription  # evitar import circular
        user = getattr(self.profile, "user", None)
        if not user:
            return

        sub, _ = Subscription.objects.get_or_create(user=user)
        now = timezone.now()

        if self.is_subscribed_admin:
            # ✅ activar suscripción manual
            end = now + timedelta(days=30)
            sub.status = Subscription.ACTIVE
            sub.current_period_end = end
            sub.override_status = Subscription.ACTIVE
            sub.override_until = end
            sub.override_reason = "Activado manualmente (admin)"
        else:
            # ❌ desactivar suscripción manual → pasa a “Pausada”
            sub.override_status = None
            sub.override_until = None
            sub.override_reason = ""
            sub.status = Subscription.PAUSED
            sub.current_period_end = now  # corta inmediatamente

        sub.save()


class GuestProfile(models.Model):
    """Datos solo para asistentes."""
    foto_personal = models.ImageField("Foto personal", upload_to="guest_photos/", blank=True, null=True)
    profile     = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="guest")
    first_name  = models.CharField("Nombre", max_length=80)
    last_name   = models.CharField("Apellido", max_length=80)
    birth_date  = models.DateField("Fecha de nacimiento",blank=True, null=True)  # <-- nuevo
    city        = models.CharField("Ciudad", max_length=100)
    created_at  = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Guest<{self.profile.user}> {self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        """Edad en años (simple y suficiente para MVP)."""
        if not self.birth_date:
            return 0
        today = date.today()
        return (
            today.year - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    @property
    def age_band(self) -> str:
        """Rango etario útil para análisis básico."""
        a = self.age
        if a < 18: return "<18"
        if a <= 24: return "18–24"
        if a <= 34: return "25–34"
        if a <= 44: return "35–44"
        if a <= 54: return "45–54"
        if a <= 64: return "55–64"
        return "65+"



class Subscription(models.Model):
    ACTIVE, PAUSED, CANCELLED = "ACTIVE", "PAUSED", "CANCELLED"
    STATUS_CHOICES = [
        (ACTIVE, "Activa"),
        (PAUSED, "Pausada"),
        (CANCELLED, "Cancelada"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="subscription")
    mp_preapproval_id = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PAUSED)
    current_period_end = models.DateTimeField(null=True, blank=True)

    # ---- Override manual (admin) ----
    override_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, null=True, blank=True,
        help_text="Si se define, este estado manda sobre el de Mercado Pago."
    )
    override_until = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha hasta la que aplica el override manual."
    )
    override_reason = models.CharField(
        max_length=200, blank=True,
        help_text="Motivo (cortesía, convenio, soporte, etc.)"
    )

    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    # Efectividad: si hay override vigente, manda; si no, usa MP
    def is_active(self):
        now = timezone.now()
        if self.override_status == self.ACTIVE and (not self.override_until or self.override_until > now):
            return True
        return self.status == self.ACTIVE and (not self.current_period_end or self.current_period_end > now)

    @staticmethod
    def active_Q(now=None):
        """Q reutilizable para filtrar por suscripción efectivamente activa (MP o override)."""
        from django.utils import timezone as _tz
        now = now or _tz.now()
        return (
            Q(status=Subscription.ACTIVE, current_period_end__gt=now) |
            Q(override_status=Subscription.ACTIVE, override_until__gt=now) |
            Q(override_status=Subscription.ACTIVE, override_until__isnull=True)
        )

    def __str__(self):
        base = f"Sub de {getattr(self.user, 'username', self.user_id)}"
        return f"{base} (efectiva={'Sí' if self.is_active() else 'No'})"