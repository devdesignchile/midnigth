from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone

User = get_user_model()

@receiver(post_save, sender=User)
def welcome_email(sender, instance, created, **kwargs):
    if not created or not instance.email:
        return

    subject = "Bienvenido a Midnight 🌙"

    full_name = (instance.get_full_name() or "").strip()
    name = f", {full_name}" if full_name else ""

    context = {
        "name": name,
        "site_url": "https://midnight.cl",
        "year": timezone.now().year,
    }

    html_content = render_to_string("accounts/welcome.html", context)
    text_content = strip_tags(html_content)  # fallback simple

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[instance.email],
        reply_to=[settings.EMAIL_HOST_USER],  # opcional, para que respondan al gmail si usas smtp gmail
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
