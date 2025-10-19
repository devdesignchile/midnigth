# app/accounts/context_processors.py
from .models import Profile

def account_flags(request):
    is_owner = False
    if request.user.is_authenticated:
        try:
            is_owner = getattr(request.user.profile, "is_owner", False)
        except Profile.DoesNotExist:
            is_owner = False
    return {"is_owner": is_owner}
