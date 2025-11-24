# app/core/admin.py
from django.contrib import admin
from .models import Commune, Tag, Venue, Event, Photo

# --- Inlines ---
class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 1
    fields = ("image", "caption", "sort_order")
    ordering = ("sort_order",)


# --- Commune ---
@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ("id","name", "region", "country", "slug")
    search_fields = ("name", "slug", "region")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


# --- Tag ---
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


# --- Venue ---
@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "Commune", "category", "address", "phone", "is_published", "clicks_count", "last_clicked_at")
    list_filter   = ("category", "is_published", "Commune")
    search_fields = ("name", "address", "phone", "Commune__name")
    list_editable = ("is_published",)
    readonly_fields = ("clicks_count", "last_clicked_at")
    ordering = ("-clicks_count", "name")

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "Commune", "venue", "category", "start_at", "is_featured", "is_published", "clicks_count", "last_clicked_at")
    list_filter   = ("category", "is_featured", "is_published", "Commune", "venue")
    search_fields = ("title", "venue__name", "Commune__name")
    list_editable = ("is_featured", "is_published")
    readonly_fields = ("clicks_count", "last_clicked_at")
    date_hierarchy = "start_at"
    ordering = ("-clicks_count", "-start_at")