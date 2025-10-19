# app/accounts/admin.py
from django.contrib import admin
from .models import Profile, OwnerProfile, GuestProfile


# --- Inlines (van dentro del admin de Profile) ---
class OwnerProfileInline(admin.StackedInline):
    model = OwnerProfile
    fk_name = "profile"          # asegura la relación correcta
    extra = 0
    can_delete = True
    verbose_name = "Dueño de local"
    verbose_name_plural = "Dueño de local"


class GuestProfileInline(admin.StackedInline):
    model = GuestProfile
    fk_name = "profile"
    extra = 0
    can_delete = True
    verbose_name = "Asistente"
    verbose_name_plural = "Asistente"


# --- Admin de Profile ---
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user_username", "user_email", "role")
    search_fields = ("user__username", "user__email")
    list_filter = ("role",)
    inlines = [OwnerProfileInline, GuestProfileInline]

    @admin.display(ordering="user__username", description="Usuario")
    def user_username(self, obj):
        return getattr(obj.user, "username", "")

    @admin.display(ordering="user__email", description="Email")
    def user_email(self, obj):
        return getattr(obj.user, "email", "")


# --- Admin de OwnerProfile (listado directo) ---
@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_username",
        "venue_name",
        "admin_name",
        "rut_comercio",
        "company_email",
        "company_domain",
        "owner_verified",
        "created_at",
    )
    search_fields = (
        "venue_name",
        "admin_name",
        "rut_comercio",
        "company_email",
        "company_domain",
        "profile__user__username",
        "profile__user__email",
    )
    list_filter = ("owner_verified", "company_domain")

    @admin.display(ordering="profile__user__username", description="Usuario")
    def user_username(self, obj):
        return getattr(obj.profile.user, "username", "")


# --- Admin de GuestProfile (listado directo) ---
@admin.register(GuestProfile)
class GuestProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user_username",
        "first_name",
        "last_name",
        "city",
        "age_display",
        "age_band_display",
        "created_at",
    )
    search_fields = (
        "first_name",
        "last_name",
        "city",
        "profile__user__username",
        "profile__user__email",
    )
    list_filter = ("city",)  # nota: age/age_band son propiedades, no van en list_filter

    @admin.display(ordering="profile__user__username", description="Usuario")
    def user_username(self, obj):
        return getattr(obj.profile.user, "username", "")

    @admin.display(description="Edad")
    def age_display(self, obj):
        return obj.age  # propiedad del modelo

    @admin.display(description="Rango etario")
    def age_band_display(self, obj):
        return obj.age_band  # propiedad del modelo
