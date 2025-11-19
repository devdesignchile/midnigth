# app/account/models.py  (ajusta la ruta si tu app es distinta)
from datetime import date, timedelta
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

User = settings.AUTH_USER_MODEL  # ej: "auth.User" o tu usuario custom


class Profile(models.Model):
    ROLE_CHOICES = (("owner", "Dueño de local"), ("guest", "Asistente"))
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.user} ({self.get_role_display()})"

    @property
    def is_owner(self): 
        return self.role == "owner"

    @property
    def is_guest(self): 
        return self.role == "guest"


class OwnerProfile(models.Model):
    # ✅ referencia directa al modelo correcto (no "accounts.Profile")
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="owner")

    venue_name = models.CharField("Nombre del local", max_length=120)
    admin_name = models.CharField("Nombre administrador", max_length=120)
    rut_comercio = models.CharField("RUT comercio", max_length=14)
    company_email = models.EmailField("Correo corporativo", unique=True)
    company_domain = models.CharField("Dominio comercial", max_length=120, unique=True)

    owner_verified = models.BooleanField(default=False)

    # ✅ checkbox real visible en el admin
    is_subscribed_admin = models.BooleanField(
        default=False,
        verbose_name="Suscrito (Admin)",
        help_text="Marcar manualmente para activar la suscripción del dueño."
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Owner<{self.profile.user}> {self.venue_name}"

    def save(self, *args, **kwargs):
        """
        Al guardar el Owner:
        - Si is_subscribed_admin=True → crea/actualiza Subscription a ACTIVA
          (override + 30 días).
        - Si False → limpia override y deja PAUSADA (corta periodo a ahora).
        Se usa update_or_create para evitar bucles.
        """
        super().save(*args, **kwargs)

        user = getattr(self.profile, "user", None)
        if not user:
            return

        now = timezone.now()
        end = now + timedelta(days=30)

        # Importa Subscription definido más abajo sin crear import circular
        # (no hace falta import explícito aquí, estamos en el mismo archivo).
        Subscription.objects.update_or_create(
            user=user,
            defaults=(
                {
                    "status": Subscription.ACTIVE,
                    "current_period_end": end,
                    "override_status": Subscription.ACTIVE,
                    "override_until": end,
                    "override_reason": "Activado manualmente (admin)",
                }
                if self.is_subscribed_admin
                else {
                    "override_status": None,
                    "override_until": None,
                    "override_reason": "",
                    "status": Subscription.PAUSED,
                    "current_period_end": now,
                }
            ),
        )


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

    def __str__(self):
        base = f"Sub de {getattr(self.user, 'username', self.user_id)}"
        return f"{base} (efectiva={'Sí' if self.is_active() else 'No'})"

    # Efectividad: si hay override vigente, manda; si no, usa MP
    def is_active(self):
        now = timezone.now()
        if self.override_status == self.ACTIVE and (self.override_until is None or self.override_until > now):
            return True
        return self.status == self.ACTIVE and (self.current_period_end is None or self.current_period_end > now)

    @staticmethod
    def active_Q(now=None):
        now = now or timezone.now()
        return (
            Q(status=Subscription.ACTIVE, current_period_end__gt=now) |
            Q(override_status=Subscription.ACTIVE, override_until__gt=now) |
            Q(override_status=Subscription.ACTIVE, override_until__isnull=True)
        )

    def save(self, *args, **kwargs):
        """
        Doble vía: al guardar la Subscription, refleja el override vigente
        en el checkbox de OwnerProfile **sin** llamar .save() del Owner
        (evita bucles).
        """
        super().save(*args, **kwargs)

        owner = getattr(getattr(self.user, "profile", None), "owner", None)
        if not owner:
            return

        now = timezone.now()
        forced_on = (
            self.override_status == self.ACTIVE and
            (self.override_until is None or self.override_until > now)
        )

        # Actualiza el checkbox sin invocar save()
        type(owner).objects.filter(pk=owner.pk).update(is_subscribed_admin=forced_on)


class GuestProfile(models.Model):
    """Datos solo para asistentes."""
    foto_personal = models.ImageField("Foto personal", upload_to="guest_photos/", blank=True, null=True)
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="guest")
    first_name = models.CharField("Nombre", max_length=80)
    last_name = models.CharField("Apellido", max_length=80)
    birth_date = models.DateField("Fecha de nacimiento", blank=True, null=True)
    city = models.CharField("Ciudad", max_length=100, blank=True)

    # 🔹 Nuevo campo relacionado a Commune
    commune = models.ForeignKey(
        "places.Commune",              # ✅ app_label.ModelName (tu app se llama "places")
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="guests",
        verbose_name="Comuna de residencia",
    )

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Guest<{self.profile.user}> {self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        if not self.birth_date:
            return 0
        today = date.today()
        return (
            today.year - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    @property
    def age_band(self) -> str:
        a = self.age
        if a < 18: return "<18"
        if a <= 24: return "18–24"
        if a <= 34: return "25–34"
        if a <= 44: return "35–44"
        if a <= 54: return "45–54"
        if a <= 64: return "55–64"
        return "65+"
