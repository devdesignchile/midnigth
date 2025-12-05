# app/core/models.py
from django.conf import settings
from django.db import models

# -------------------------
# City (para armar URLs tipo /ciudad/santiago y filtrar)
# -------------------------
class Commune(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)  # ej: "santiago"
    region = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=80, default="Chile")
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lon = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    image = models.ImageField(upload_to="communes/%Y/%m/", blank=True)
    def __str__(self):
        return self.name


# -------------------------
# Tag (chips tipo "Bailable", "Electrónica", "Terraza")
# -------------------------
class Tag(models.Model):
    name = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.name


# -------------------------
# Venue (tu "lugar": discoteque, pub, etc.)
# -------------------------
class Venue(models.Model):
    CATEGORY_CHOICES = [
        ("discoteque", "Discoteque"),
        ("pub", "Pub"),
        ("restaurant", "Restaurante"),
        ("rooftop", "Rooftop"),
        ("other", "Otro"),                                                                                                                                                                                                                                                                                                                          
    ]

    PAYMENT_CHOICES = [
        ("Tarjeta", "Tarjeta"),
        ("Efectivo", "Efectivo"),   
        ("Transferencia", "Transferencia"),
        ("Tarjeta y Efectivo", "Tarjeta y Efectivo"),
        ("Tarjeta y Transferencia", "Tarjeta y Transferencia"),
        ("Efectivo y Transferencia", "Efectivo y Transferencia"),
        ("Todo medio de pago", "Todo medio de pago"),
    ]

    Commune = models.ForeignKey(Commune, on_delete=models.PROTECT, related_name="venues")
    # Opcional: dueño (para que él edite su ficha)
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="venues"
    )

    # HERO / encabezado
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=210, unique=True)  # ej: "club-midnight-santiago"
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    cover_image = models.ImageField(upload_to="venues/covers/%Y/%m/", blank=True)
    vibe_tags = models.ManyToManyField(Tag, blank=True, related_name="venues")  # chips como "Bailable"
    logo = models.ImageField(upload_to="venues/logos/%Y/%m/", blank=True)

    # INFO del lugar (sección "Sobre el lugar")
    description = models.TextField(blank=True)
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)  # 18+
    dress_code = models.CharField(max_length=120, blank=True)
    payment_methods = models.CharField(max_length=50, choices=PAYMENT_CHOICES, null=True, blank=True)
    experience_venue = models.CharField(max_length=120, blank=True)

    # CONTACTO & REDES (sidebar)
    address = models.CharField(max_length=220, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(blank=True)
    instagram = models.URLField(blank=True)

    # BOTÓN "Reservar / Entradas" del hero
    reservation_url = models.URLField(blank=True) 

    # HORARIOS (lo que muestras tipo "Vie–Sáb 21:00–04:00")
    hours_short = models.CharField(max_length=80, blank=True)

    # BARRA (chips + recomendado + promos + enlaces)
    highlights_1 = models.CharField(max_length=120, blank=True, null=True)
    highlights_2 = models.CharField(max_length=120, blank=True, null=True)
    highlights_3 = models.CharField(max_length=120, blank=True, null=True)
    recommended_title = models.CharField(max_length=120, blank=True, default="Recomendado del bartender")
    recommended_body = models.TextField(blank=True)
    menu_pdf = models.FileField(blank=True)
    menu_qr_url = models.URLField(blank=True)
    vgt_promos_1 = models.CharField(max_length=120, blank=True, null=True)
    vgt_promos_2 = models.CharField(max_length=120, blank=True, null=True)
    vgt_promos_3 = models.CharField(max_length=120, blank=True, null=True)
    gallery_venue = models.ImageField(upload_to="gallery/%Y/%m/", blank=True, null=True)
    # Publicación mínima (para ocultar si no está lista)
    is_published = models.BooleanField(default=True)
    clicks_count = models.PositiveIntegerField(default=0)
    last_clicked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


# -------------------------
# Event (para "Line-up destacado" y "Próximos eventos")
# -------------------------
class Event(models.Model):
    CATEGORY_CHOICES = [
        ("party", "Carrete/Fiesta"),
        ("concert", "Concierto"),
        ("standup", "Stand-up"),
        ("electronic", "Electrónica"),
        ("other", "Otro"),
    ]

    Commune = models.ForeignKey(Commune, on_delete=models.PROTECT, related_name="events")
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events", null=True, blank=True)

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=210, unique=True)  # ej: "dj-nova-noche-electronica-santiago-20251017"
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)

    # Agenda / flyer (lo que muestras en carruseles y grillas)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    flyer_image = models.ImageField(
    upload_to="events/flyers/%Y/%m/",
    blank=True,
    max_length=300,  # por ejemplo
)

    # Textos cortos del flyer/carrusel
    eyebrow_text = models.CharField(max_length=60, blank=True)  # "Viernes · 22:00"
    badge_text = models.CharField(max_length=60, blank=True)    # "Preventa", "2x1", etc.

    # CTA "Comprar"
    external_ticket_url = models.URLField(blank=True)

    # Aparece en "Line-up destacado" del hero
    is_featured = models.BooleanField(default=False)
    feature_order = models.PositiveSmallIntegerField(default=0)

    is_published = models.BooleanField(default=True)
    clicks_count = models.PositiveIntegerField(default=0)
    last_clicked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title


# -------------------------
# Galería de fotos del venue (para la sección "Galería")
# -------------------------
class Photo(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="venues/gallery/%Y/%m/")
    caption = models.CharField(max_length=160, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return self.caption or f"Foto {self.pk}"
