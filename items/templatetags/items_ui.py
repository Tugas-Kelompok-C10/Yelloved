"""Presentation labels only; stored item choices remain unchanged."""
from django import template

register = template.Library()


@register.filter
def condition_badge(value):
    return {'like_new': 'LIGHTLY USED', 'good': 'WELL USED', 'fair': 'HEAVILY USED',
            'new': 'NEW'}.get(value, 'PRELOVED')


@register.filter
def listing_badge(value):
    return {'sale': 'SELL', 'free': 'FREE', 'swap': 'SWAP'}.get(value, 'PRELOVED')

# Translate application UI labels only, never item titles/descriptions or usernames.
UI_TEXT = {
    'Semua kategori': 'All categories', 'Semua kondisi': 'All conditions',
    'Semua tipe': 'All listing types', 'Semua status': 'All statuses',
    'Elektronik': 'Electronics', 'Buku & Keperluan Kuliah': 'Books & Study',
    'Perlengkapan Kos': 'Dorm Essentials', 'Alat Masak & Houseware': 'Kitchen & Houseware',
    'Aksesoris': 'Accessories', 'Sangat Baik': 'Very good', 'Baik': 'Good',
    'Layak Pakai': 'Well used', 'Baru': 'New', 'Jual': 'Sell', 'Gratis': 'Free',
    'Tukar': 'Exchange', 'Tersedia': 'Available', 'Terjual': 'Sold',
    'Tidak Tersedia': 'Unavailable', 'Menunggu': 'Pending', 'Diterima': 'Accepted',
    'Ditolak': 'Rejected', 'Dibatalkan': 'Cancelled',
    'Nama barang': 'Item title', 'Deskripsi': 'Description', 'Kategori': 'Category',
    'Kondisi': 'Condition', 'Tipe listing': 'Listing type', 'Harga': 'Price',
    'Lokasi': 'Location', 'URL foto': 'Photo URL', 'Foto': 'Photo', 'Image': 'Photo',
    'Pesan': 'Message', 'Barang yang ditukarkan': 'Item to exchange',
    'Pilih barangmu': 'Select your item', '---------': 'Select an option',
    'Wajib untuk listing bertipe Tukar.': 'Required for exchange listings.',
    'Dalam rupiah. Wajib untuk Jual; dikosongkan untuk Gratis/Tukar.': 'In Rupiah. Required for sale listings; leave blank for free or exchange items.',
    'Pilih foto dari galeri atau penyimpanan perangkat (JPG, PNG, WebP; maksimal 5 MB).': 'Choose a photo from your device (JPG, PNG, WebP; maximum 5 MB).',
    'Contoh: Kukusan, Depok. Hindari alamat rumah lengkap.': 'For example: Kukusan, Depok. Avoid sharing your full home address.',
    'Perkenalkan diri dan sebutkan waktu/lokasi COD yang kamu inginkan.': 'Introduce yourself and suggest a time and place to meet.',
    'Harga wajib diisi untuk barang yang dijual.': 'A price is required for items listed for sale.',
    'Pilih foto item dari galeri atau penyimpanan perangkat.': 'Choose an item photo from your device.',
    'Kamu sudah mengajukan request untuk barang ini.': 'You already have a pending request for this item.',
    'Harga belum tersedia': 'Price not available',
    'Ukuran foto maksimal 5 MB.': 'The maximum photo size is 5 MB.',
    'Gunakan URL foto HTTP/HTTPS atau aset katalog lokal yang valid.': 'Use an HTTP/HTTPS photo URL or a valid local catalogue asset.',
    'Pilih barang yang ingin kamu tukarkan.': 'Select the item you want to exchange.',
    'Barang ini sudah tidak tersedia.': 'This item is no longer available.',
    'Kamu tidak bisa merequest barangmu sendiri.': 'You cannot request your own item.',
    'Barang tukar harus milikmu dan masih tersedia.': 'The exchange item must belong to you and be available.',
    'Foto barang': 'Item photo',

}


@register.filter
def ui_text(value):
    return UI_TEXT.get(str(value), value)


@register.filter
def english_widget(bound_field):
    """Render a copy with English UI choices/placeholder, preserving submitted values."""
    from copy import copy, deepcopy
    from django import forms
    field = copy(bound_field)
    field.field = deepcopy(bound_field.field)
    if isinstance(field.field, forms.ChoiceField) and not isinstance(field.field, forms.ModelChoiceField):
        field.field.choices = [(value, ui_text(label)) for value, label in field.field.choices]
    if 'placeholder' in field.field.widget.attrs:
        field.field.widget.attrs['placeholder'] = ui_text(field.field.widget.attrs['placeholder'])
    return field.as_widget()
