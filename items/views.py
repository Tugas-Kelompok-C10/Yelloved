from django.http import Http404
from django.shortcuts import render


# Koleksi contoh untuk Explore; belum terhubung ke inventaris atau transaksi.
DUMMY_ITEMS = (
    {"id": 1, "name": "Kemeja Biru Motif", "price": "Rp45.000", "condition": "Like New", "category": "Fashion", "location": "Fasilkom UI, Depok", "image": "img/items/shirt.jpg", "description": "Kemeja ukuran M dengan warna biru dan motif kecil. Baru dipakai beberapa kali, bersih dan tanpa noda."},
    {"id": 2, "name": "Lampu Belajar Abu-abu", "price": "Rp60.000", "condition": "Good", "category": "Perlengkapan Kos", "location": "Kukusan, Depok", "image": "img/items/lamp.jpg", "description": "Lampu meja untuk menemani belajar di kos. Berfungsi baik dengan sedikit bekas pemakaian pada bagian dasar."},
    {"id": 3, "name": "Kalkulator Meja", "price": "Rp80.000", "condition": "Like New", "category": "Elektronik", "location": "Asrama UI, Depok", "image": "img/items/calculator.jpg", "description": "Kalkulator meja untuk perhitungan sehari-hari. Tombol dan layar berfungsi baik, cocok untuk kebutuhan kuliah."},
    {"id": 4, "name": "Buku Milk and Honey", "price": "Free", "condition": "Good", "category": "Buku", "location": "Pondok Cina, Depok", "image": "img/items/book.jpg", "description": "Kumpulan puisi untuk teman membaca di sela kuliah. Semua halaman lengkap, dengan sedikit lipatan pada sampul. Siap diberikan ke pembaca berikutnya."},
    {"id": 5, "name": "Tas Tangan Anyaman", "price": "Rp25.000", "condition": "Good", "category": "Fashion", "location": "Beji, Depok", "image": "img/items/tote.jpg", "description": "Tas tangan anyaman untuk membawa perlengkapan harian. Bersih dan siap dipakai kembali."},
    {"id": 6, "name": "Set Pensil Warna", "price": "Free", "condition": "Like New", "category": "Perlengkapan Kos", "location": "Margonda, Depok", "image": "img/items/organizer.jpg", "description": "Set pensil warna untuk menggambar dan membuat catatan kreatif. Diberikan gratis karena sudah tidak digunakan."},
)
CONDITIONS = ("Like New", "Good")
CATEGORIES = ("Fashion", "Perlengkapan Kos", "Elektronik", "Buku")


def explore_items(request):
    query = request.GET.get("q", "").strip()
    condition = request.GET.get("condition", "")
    category = request.GET.get("category", "")
    condition = condition if condition in CONDITIONS else ""
    category = category if category in CATEGORIES else ""
    items = [
        item for item in DUMMY_ITEMS
        if (not query or query.casefold() in f"{item['name']} {item['location']} {item['category']}".casefold())
        and (not condition or item["condition"] == condition)
        and (not category or item["category"] == category)
    ]
    return render(request, "items/explore.html", {
        "name": "Yelloved", "items": items, "query": query,
        "condition": condition, "category": category,
        "conditions": CONDITIONS, "categories": CATEGORIES,
    })


def item_detail(request, item_id):
    item = next((item for item in DUMMY_ITEMS if item["id"] == item_id), None)
    if item is None:
        raise Http404("Item tidak ditemukan")
    return render(request, "items/detail.html", {"name": "Yelloved", "item": item})
