# app/places/admin.py
from django.contrib import admin
from .models import Venue, Event, Photo, Commune   # importa tus modelos


admin.site.register(Venue)
admin.site.register(Event)
admin.site.register(Photo)
admin.site.register(Commune)
# app/places/admin.py

