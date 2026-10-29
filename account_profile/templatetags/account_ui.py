"""English presentation labels without changing other apps' stored choices."""
from django import template

register = template.Library()


@register.filter
def account_label(value):
    return {
        "Elektronik": "Electronics", "Buku & Keperluan Kuliah": "Books & Study",
        "Perlengkapan Kos": "Home & Living", "Alat Masak & Houseware": "Kitchen & Houseware",
        "Aksesoris": "Accessories", "Jual": "Sell", "Gratis": "Free", "Tukar": "Trade",
        "Tersedia": "Available", "Terjual": "Sold", "Tidak Tersedia": "Unavailable",
    }.get(value, value)
