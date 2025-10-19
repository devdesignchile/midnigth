# app/accounts/models.py
from django.conf import settings
# app/accounts/models.py
from datetime import date
from django.db import models
from django.utils import timezone
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
    """Datos solo para dueños de locales."""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name="owner")

    # Campos para registro:
    venue_name     = models.CharField("Nombre del local", max_length=120)
    admin_name     = models.CharField("Nombre administrador", max_length=120)
    rut_comercio   = models.CharField("RUT comercio", max_length=14)  # ej: 12.345.678-5
    company_email  = models.EmailField("Correo corporativo", unique=True)
    company_domain = models.CharField("Dominio comercial", max_length=120, unique=True)

    # Opcionales de flujo:
    owner_verified = models.BooleanField(default=False)
    created_at     = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Owner<{self.profile.user}> {self.venue_name}"


class GuestProfile(models.Model):
    """Datos solo para asistentes."""
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
