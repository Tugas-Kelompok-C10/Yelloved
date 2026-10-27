"""Katalog seed preloved kampus, bukan harga/penawaran produk sumber API."""
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
import json

USD_TO_IDR = Decimal('16000')
LOCATIONS = ('Area UI, Depok', 'Pondok Cina, Depok', 'Kukusan, Depok', 'Beji, Depok', 'Margonda, Depok', 'Depok')

# Harga seed ditentukan sebagai harga preloved IDR, tidak mengikuti harga ritel API.
SEED_CATALOG = (
    ('fashion', 'Kaos Katun Polos', 20000),
    ('fashion', 'Kemeja Flanel Kotak', 45000),
    ('fashion', 'Hoodie Abu-abu', 75000),
    ('fashion', 'Celana Bahan Kuliah', 50000),
    ('fashion', 'Jaket Denim', 90000),
    ('fashion', 'Tote Bag Kanvas', 25000),
    ('fashion', 'Ransel Kuliah', 65000),
    ('fashion', 'Sepatu Kanvas', 80000),
    ('fashion', 'Kemeja Lengan Panjang', 40000),
    ('skincare', 'Facial Cleanser', 35000),
    ('fashion', 'Celana Jeans', 60000),
    ('fashion', 'Jaket Hujan Ringkas', 35000),
    ('fashion', 'Sweater Rajut', 55000),
    ('fashion', 'Sepatu Lari Harian', 120000),
    ('books', 'Buku Pengantar Pemrograman', 45000),
    ('books', 'Buku Kalkulus Dasar', 50000),
    ('books', 'Novel Bekas Bacaan Santai', 25000),
    ('books', 'Kalkulator Scientific', 85000),
    ('books', 'Binder A5 dengan Pembatas', 20000),
    ('books', 'Set Alat Tulis Kuliah', 15000),
    ('books', 'Buku Statistika Dasar', 40000),
    ('books', 'Buku Bahasa Inggris Akademik', 35000),
    ('books', 'Papan Jalan untuk Catatan', 10000),
    ('books', 'Tempat Pensil Kanvas', 10000),
    ('electronics', 'Headset untuk Kelas Daring', 65000),
    ('electronics', 'Keyboard USB', 75000),
    ('electronics', 'Mouse Nirkabel', 45000),
    ('electronics', 'Power Bank 10000 mAh', 90000),
    ('electronics', 'Lampu Belajar Meja', 60000),
    ('electronics', 'Kipas Meja Kecil', 85000),
    ('electronics', 'Monitor Bekas 22 Inci', 1000000),
    ('electronics', 'Laptop Bekas untuk Kuliah', 2500000),
    ('electronics', 'Headphone Kabel', 55000),
    ('electronics', 'Mouse USB', 30000),
    ('electronics', 'Keyboard Ringkas', 120000),
    ('electronics', 'Lampu Belajar Jepit', 45000),
    ('electronics', 'Laptop Bekas RAM 8 GB', 3200000),
    ('electronics', 'Monitor Bekas 24 Inci', 1300000),
    ('home', 'Meja Lipat Belajar', 100000),
    ('home', 'Kursi Belajar Kos', 125000),
    ('home', 'Rak Buku Tiga Susun', 85000),
    ('home', 'Rak Pakaian Bongkar Pasang', 90000),
    ('home', 'Set Hanger Pakaian', 20000),
    ('home', 'Organizer Meja', 25000),
    ('home', 'Dispenser Air Meja', 150000),
    ('home', 'Rice Cooker Kecil', 175000),
    ('kitchen_houseware', 'Set Alat Masak', 70000),
    ('home', 'Lemari Kain untuk Kos', 120000),
    ('home', 'Rak Sepatu Ringkas', 45000),
    ('home', 'Kotak Penyimpanan Buku', 25000),
    ('home', 'Panci Kecil Bertutup', 40000),
    ('home', 'Kotak Bekal Kuliah', 25000),
    ('home', 'Gelas dan Cangkir Keramik', 20000),
    ('accessories', 'Dompet Kartu Mahasiswa', 15000),
    ('accessories', 'Topi untuk Aktivitas Kampus', 20000),
    ('accessories', 'Tas Selempang Ringkas', 35000),
    ('accessories', 'Lanyard Kartu Kampus', 10000),
    ('accessories', 'Pouch Perlengkapan Kuliah', 15000),
    ('books', 'Novel Petualangan Bekas', 30000),
    ('home', 'Rak Dapur Mini', 60000),
)

ELIGIBLE_CATEGORIES = {
    'mens-shirts', 'tops', 'mens-shoes', 'womens-shoes', 'womens-bags',
    'laptops', 'mobile-accessories', 'kitchen-accessories', 'home-decoration',
    'smartphones', 'tablets', 'sports-accessories', 'womens-dresses',
}
# Sumber yang ditolak tidak dijadikan identitas seed maupun ditampilkan ulang.
EXCLUDED_WORDS = ('rolex', 'echo', 'homepod', 'luxury', 'gucci', 'prada', 'chanel',
                  'louis vuitton', 'hermes', 'dior', 'airpods max', 'watch',
                  'camera pedestal', 'microwave', 'swing', 'sink')


def rupiah_from_usd(price):
    # Dukungan tampilan data lama saja; seed baru memakai harga preloved terkurasi.
    return (Decimal(str(price)) * USD_TO_IDR / 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * 1000


def is_eligible(product):
    title = product['title'].casefold()
    return product['category'] in ELIGIBLE_CATEGORIES and not any(word in title for word in EXCLUDED_WORDS)


@lru_cache(maxsize=1)
def catalog_photos():
    return json.loads(
        Path(__file__).with_name('catalog_photos.json').read_text(encoding='utf-8')
    )


def localize_product(product, index=0):
    if not is_eligible(product):
        return None
    photos = catalog_photos()
    photo = photos[index % len(photos)]
    profile = photo['profile']
    category, _, price = SEED_CATALOG[profile]
    title = photo['title']
    condition = ('like_new', 'good', 'fair')[index % 3]
    notes = {'like_new': 'Terawat dengan sedikit bekas pemakaian.',
             'good': 'Kondisi baik dengan bekas pemakaian wajar.',
             'fair': 'Masih layak dipakai, dengan bekas pemakaian yang terlihat.'}
    # Sebagian barang murah diberikan gratis; laptop/monitor tetap berharga wajar.
    free = profile in (9, 18, 23, 42, 52, 56)
    return {'title': title, 'category': category, 'condition': condition,
            'description': f'{title} preloved untuk kegiatan kuliah dan kebutuhan kos. {notes[condition]} Bisa diambil di sekitar kampus sesuai lokasi listing.',
            'location': LOCATIONS[index % len(LOCATIONS)],
            'price': None if free else Decimal(price), 'listing_type': 'free' if free else 'sale',
            'image_url': photo['image_url']}
