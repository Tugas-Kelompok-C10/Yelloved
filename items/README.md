# Items Management

Modul ini memakai `settings.AUTH_USER_MODEL` dan route project yang sudah ada, `/explore/`. Tidak memerlukan perubahan settings, base template, atau aplikasi lain. yay

## Approved Public API sources

Items uses [DummyJSON Products](https://dummyjson.com/docs/products), with data
requested from `https://dummyjson.com/products?limit=0` by the existing import
command. No other product API is used. The 20 migration seeds remain frozen local
records inspired by this catalogue; migrations and Explore never fetch the API.
Local photo files and their existing licence attribution remain unchanged.

The other approved sources belong to separate integration concerns:

- [DummyJSON Auth](https://dummyjson.com/docs/auth) and
  [DummyJSON Users](https://dummyjson.com/users): authentication/user demo data;
  Items does not replace Django authentication or import these users as real accounts.
- [API Wilayah Indonesia](https://github.com/emsifa/api-wilayah-indonesia): an approved
  source for administrative location data if a location selector is added later.
  The current Items location field remains free text; this API is not integrated yet.

## Setup dan data awal

```sh
env/bin/python3 manage.py makemigrations items
env/bin/python3 manage.py migrate
env/bin/python3 manage.py import_dummyjson_items --limit 100 --refresh
env/bin/python3 manage.py check
env/bin/python3 manage.py test items
```

Command mengambil katalog sumber dari DummyJSON (`https://dummyjson.com/products?limit=0`, timeout 30 detik), menolak kategori/produk luxury, kendaraan, kosmetik, wastafel, dan produk yang tidak cocok untuk mahasiswa. Sumber API: https://dummyjson.com/docs/products.

Identitas `external_id` dari produk yang lolos dipakai untuk seed deterministik. Data yang tampil **merupakan katalog demo terkurasi**, bukan terjemahan atau penawaran produk asli DummyJSON. Nama, deskripsi, lokasi, harga, dan kondisi seed berasal dari `items/import_catalog.py`; harga ritel USD API tidak dipakai sebagai harga listing. Nama tidak mempertahankan merek luxury. Setiap seed ditempatkan di Area UI/Pondok Cina/Kukusan/Beji/Margonda/Depok. Tidak ada fetch API saat membuka Explore.

Kategori: Fashion, Buku & Keperluan Kuliah, Elektronik, Perlengkapan Kos, Aksesoris. Kondisi: Sangat Baik, Baik, Layak Pakai. Harga fashion Rp10.000–Rp150.000, buku/kuliah Rp10.000–Rp200.000, elektronik kecil Rp30.000–Rp500.000, laptop/monitor Rp1.000.000–Rp5.000.000, kos Rp20.000–Rp400.000. Beberapa barang murah diberi label Gratis. Tidak ada kondisi Baru pada seed atau pilihan form baru.

Harga disimpan sebagai IDR dan diformat seperti `Rp45.000`. Konversi tetap Rp16.000/USD hanya dipertahankan untuk tampilan data lama yang masih bermata uang USD; data manual tidak dikonversi atau diubah di database.

`--limit` memilih 50–100 seed (default 100), sesuai 100 foto lokal yang telah dikurasi. Kategori identitas sumber diperluas untuk memenuhi 100 seed, tetapi barang yang ditampilkan tetap katalog preloved mahasiswa terkurasi. Kurang dari 50 hasil membatalkan impor tanpa perubahan database. Semua data divalidasi dahulu dan penulisan memakai transaksi. `external_id` unik mencegah duplikasi pada impor ulang.

`--refresh` mengelola item impor lama tanpa owner serta item impor yang sudah dimiliki penjual demo khusus. Item manual dan item milik pengguna asli tidak pernah ditimpa/dihapus. Konflik ID dengan item manual membatalkan impor. Migrasi kondisi hanya mengubah choices, tanpa menulis ulang data manual.

Setiap 100 seed dipetakan ke 100 foto asli yang berbeda di `static/img/items/catalog/item-001.webp` sampai `item-100.webp`. Pemetaan judul, profil harga, sumber asli, pembuat, lisensi, dimensi, dan checksum ada di `items/catalog_photos.json`. URL yang disimpan di database bersifat lokal `/static/img/items/catalog/...`, sehingga tidak ada hotlink saat aplikasi dimuat. Import ulang memakai pemetaan foto yang sama, tanpa perlu mengunduh foto saat runtime.

Foto ditemukan melalui Openverse dan diunduh dari halaman/file sumber, terutama Flickr, dengan lisensi CC BY / CC BY-SA. Atribusi lengkap per file berada di `static/img/items/SOURCES.md`, yang ditautkan dari halaman detail. Foto hanya diperkecil proporsional (maksimal 1100 px) dan dikonversi WebP kualitas 84; tidak diedit background atau di-crop. Lisensi foto asli tetap berlaku terhadap versi WebP. Semua foto adalah ilustrasi katalog demo, bukan bukti kondisi barang penjual.

Card memakai `object-fit: cover`; detail memakai `contain` untuk melihat barang secara utuh. SVG kategori dipakai hanya bila foto kosong/gagal dimuat, termasuk card hasil AJAX. Foto pengguna manual tetap dipakai; form pengguna tetap mewajibkan URL HTTP/HTTPS. Validator model mengizinkan hanya URL HTTP/HTTPS atau pola path lokal katalog yang dibatasi.

## Demo CRUD

1. Buka Explore, klik **+ Jual Barang**. Guest diarahkan login dengan `next=/explore/create/`.
2. Setelah login, isi form (termasuk URL foto HTTP/HTTPS), lalu Simpan Item. Pemilik diatur otomatis oleh server.
3. Item langsung tampil di Explore dan hasil JSON; detail menampilkan Edit Item / Status dan Hapus Item hanya kepada pemilik.
4. Edit data/status, lalu simpan. Hapus Item membuka konfirmasi; penghapusan hanya terjadi setelah POST Ya, Hapus Item.
5. Item seed tidak menampilkan tombol pengelolaan. Pengguna lain yang memaksa URL edit/hapus mendapatkan 403.

## Routes

| URL | Nama URL | Fungsi |
| --- | --- | --- |
| `/explore/` | `items:explore_items` | Katalog database dan filter GET |
| `/explore/api/` | `items:items_json` | GET JSON publik, filter dan pagination |
| `/explore/create/` | `items:item_create` | GET/POST tambah item, wajib login |
| `/explore/<id>/` | `items:item_detail` | Detail item |
| `/explore/<id>/edit/` | `items:item_update` | GET/POST edit, hanya pemilik |
| `/explore/<id>/delete/` | `items:item_delete` | GET konfirmasi, POST hapus, hanya pemilik |

Filter: `q` (judul/deskripsi), `category`, `condition`, `listing_type`, `status`, dan `page` (12 barang per halaman). Nilai filter mengikuti choices model. Filter tidak valid menghasilkan JSON 400. JSON hanya berisi field publik serta HTML partial yang di-escape Django; tidak memuat informasi akun/kontak. AJAX memakai debounce 300 ms, AbortController, loading/error/retry/empty state. Form GET dan pagination tetap bekerja tanpa JavaScript.

Identitas penjual hanya tampil pada detail untuk pengguna login. Guest diarahkan login dengan `next` saat membuka create/edit/delete. Pengguna login selain pemilik mendapat 403 ketika memaksa edit/hapus. POST memakai CSRF dan kepemilikan ditetapkan server. Owner dapat mengubah status melalui form Edit Item / Status.

Tombol “Tertarik dengan Item Ini” hanya menampilkan pesan lokal; belum ada chat, transaksi, atau matching. Semua CSS khusus items berada di `static/css/explore.css`, scoped `.explore-page`, memakai token global Yelloved.

## Penjual demo katalog dan request

Importer membuat akun khusus `yelloved_community` (nama **Yelloved Community**) dengan password tidak dapat digunakan, tanpa hak staff/admin. Akun lain dengan username sama tidak diambil alih. Listing impor tanpa pemilik dipindahkan ke penjual demo. `source` disimpan sebagai `user` karena endpoint dan validasi Item Matching hanya menerima user listings; `external_id` tetap menjadi identitas API. Properti `Item.is_catalog` mempertahankan label koleksi inspirasi dan kredit foto. Tidak ada perubahan model/logic Item Matching.

Refresh hanya mengelola data lama `source=dummyjson, owner=NULL` atau katalog ber-`external_id` milik akun demo tersebut. Item yang sudah dimiliki pengguna lain dan listing manual tanpa external_id tetap dilindungi. Katalog tidak dapat diedit/dihapus melalui CRUD biasa, termasuk oleh penjual demo.

Send Offer memakai POST+CSRF ke `item_matching:request_create`, dengan pesan/barang tukar dari form matching yang asli. Sukses mengikuti redirect backend ke daftar request terkirim. Nominal penawaran tidak memiliki input, tidak dikirim, dan belum disimpan; kesepakatan dilakukan melalui chat/request. Guest harus login dan pemilik tidak dapat merequest itemnya sendiri.

## Automatic offline catalogue (20 items)

`python manage.py migrate` installs `0008_seed_catalogue_items`: exactly 20 curated
student/dorm demo listings, inspired by DummyJSON Products and frozen directly in
the migration. No API call, photo download, or import command is needed. Existing
local catalogue photos are reused; attribution remains in `static/img/items/SOURCES.md`.

Local `external_id` values `10000001`–`10000020` are reserved migration seed IDs,
not real DummyJSON product IDs. Prices are affordable preloved IDR values; two
listings are free. Existing manual listings and previous API imports are retained,
so an already populated database can contain more than 20 total items.

The dedicated seller is **Yelloved Community** (`yelloved_community`, unusable
password). `source='user'` preserves compatibility with the existing matching
endpoint; demo ownership plus reserved `external_id` identifies catalogue records.
A conflicting real account or item aborts the migration instead of taking it over.
Forward replay does not duplicate or reset listings. Reverse deletes only matching
seed records, preserves repurposed/manual records, and keeps the demo account.
The optional API `--refresh` command also preserves these 20 offline seeds.
