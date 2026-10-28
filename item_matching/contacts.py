"""Contact details revealed to the two parties of an accepted match."""
import re


def whatsapp_url(phone):
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('0'):
        digits = '62' + digits[1:]
    elif digits.startswith('8'):
        digits = '62' + digits
    return f'https://wa.me/{digits}' if len(digits) >= 8 else ''


def contact_for(user):
    """Phone from the user's account profile, or None when they have not set one."""
    profile = getattr(user, 'account_profile', None)  # missing profile -> AttributeError subclass
    phone = (profile.phone_number if profile else '').strip()
    return {'phone': phone, 'wa_url': whatsapp_url(phone)} if phone else None
