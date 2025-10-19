# app/core/dev_views.py
from types import SimpleNamespace as NS
from django.views.generic import TemplateView
from django.utils import timezone

def m2m(items):
    """Emula ManyToMany para .all en el template."""
    return NS(all=items)

class DevVenuePreview(TemplateView):
    # tu archivo está en templates/detail.html
    template_name = "detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ---- venue fake con los campos que usa tu template ----
        city = NS(name="Santiago", region="RM")
        venue = NS(
            name="Club Midnight",
            slug="club-midnight-santiago",
            city=city,
            category="discoteque",
            get_category_display=lambda: "Discoteque",
            cover_image=NS(url="https://images.unsplash.com/photo-1514525253161-7a46d19cd819?q=80&w=1920&auto=format&fit=crop"),
            vibe_tags=m2m([NS(name="Bailable")]),
            hours_short="Vie–Sáb 21:00–04:00",
            reservation_url="#",
            instagram="https://instagram.com/clubmidnight",
            website="https://clubmidnight.example",
            description=("Pista central con sistema de sonido de alta fidelidad, "
                         "electrónica y pop comercial, shows invitados y luces inmersivas."),
            min_age=18,
            dress_code="Smart casual",
            payment_methods=["Tarjeta", "Efectivo"],
            address="Av. Siempre Viva 123, Providencia",
            lat=-33.4263, lon=-70.6090,
            phone="+56 9 1111 1111",
            bar_highlights=["Signature: <b>Negroni Midnight</b>", "Mocktails sin alcohol", "Botellas para mesa"],
            bar_recommended_title="Recomendado del bartender",
            bar_recommended_body="Bitter, vermouth rosso y gin con twist de naranja.",
            bar_promos=["Happy Hour jueves 20–23 h", "Lista free hasta 23 h (eventos seleccionados)"],
            bar_menu_pdf="#",
            bar_menu_qr_url="#",
            happy_hour_note="Happy Hour: Jue 20:00–23:00",
            owner_user_id=None,   # para ocultar botón Editar en preview
            get_absolute_url="/lugar/club-midnight-santiago/",
        )

        # ---- eventos (destacados y próximos) ----
        flyer1 = "https://images.unsplash.com/photo-1503341455253-b2e723bb3dbb?q=80&w=1920&auto=format&fit=crop"
        flyer2 = "https://images.unsplash.com/photo-1508186225823-0963cf9ab0de?q=80&w=1920&auto=format&fit=crop"

        featured_events = [
            NS(slug="noche-electronica",
               title="DJ NOVA — Noche Electrónica",
               flyer_image=NS(url=flyer1),
               eyebrow_text="Viernes · 22:00",
               venue=venue,
               external_ticket_url="#"),
            NS(slug="reggaeton-party",
               title="Reggaetón Party — Live MC",
               flyer_image=NS(url=flyer2),
               eyebrow_text="Sábado · 23:00",
               venue=venue,
               external_ticket_url="#"),
        ]

        upcoming_events = [
            NS(title="Noche Electrónica", flyer_image=NS(url=flyer1),
               start_at=timezone.now(), badge_text="Preventa", external_ticket_url="#"),
            NS(title="Reggaetón Party", flyer_image=NS(url=flyer2),
               start_at=timezone.now(), badge_text="Puerta $8.000", external_ticket_url="#"),
            NS(title="Full Hits", flyer_image=NS(url=flyer1),
               start_at=timezone.now(), badge_text="2x1 antes 22h", external_ticket_url="#"),
            NS(title="Old School Night", flyer_image=NS(url=flyer2),
               start_at=timezone.now(), badge_text="Lista free", external_ticket_url="#"),
        ]

        # ---- galería ----
        gallery_urls = [
            "https://images.unsplash.com/photo-1508186225823-0963cf9ab0de?q=80&w=1800&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1521337580473-b7e994a3c43f?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1504674900247-0877df9cc836?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1503341455253-b2e723bb3dbb?q=80&w=1600&auto=format&fit=crop",
            "https://images.unsplash.com/photo-1469474968028-56623f02e42e?q=80&w=1600&auto=format&fit=crop",
        ]
        gallery = [NS(image=NS(url=u), caption="") for u in gallery_urls]

        # ---- relacionados ----
        related_venues = [
            NS(name="Club Aurora", city=city, category="discoteque",
               get_category_display=lambda: "Discoteque",
               cover_image=NS(url="https://images.unsplash.com/photo-1563729784474-d77dbb933a9f?q=80&w=1200&auto=format&fit=crop"),
               vibe_tags=m2m([NS(name="Electrónica")]),
               get_absolute_url="/lugar/club-aurora/"),
            NS(name="Bar Prisma", city=city, category="pub",
               get_category_display=lambda: "Pub",
               cover_image=NS(url="https://images.unsplash.com/photo-1504639725590-34d0984388bd?q=80&w=1200&auto=format&fit=crop"),
               vibe_tags=m2m([NS(name="Coctelería")]),
               get_absolute_url="/lugar/bar-prisma/"),
        ]

        ctx.update({
            "venue": venue,
            "featured_events": featured_events,
            "upcoming_events": upcoming_events,
            "gallery": gallery,
            "related_venues": related_venues,
            "edit_mode": False,
        })
        return ctx
