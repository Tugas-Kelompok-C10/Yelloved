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

## Item photos and create status

The Add/Edit form accepts optional `images` uploads: up to five total photos per
item, JPEG/PNG/WebP only, maximum 5 MB each. Uploads are verified server-side as
images, not just by filename. A small local preview allows removal before submit;
Edit also allows selecting existing photos for removal. With no photo, the
existing category fallback remains available.

`0009_itemimage` creates the ordered `ItemImage` relation and links existing
uploaded photo filenames without copying files. Catalogue URLs/photos remain
unchanged. The first retained photo is the primary Catalogue image; newly uploaded
photos are appended in selection order. The legacy primary image field is kept in
sync for existing consumers. Detail thumbnails show only actual uploaded photos.

Create ignores submitted status and always sets `available`; only the owner Edit
form exposes status. Photo deletion IDs are restricted to that item's images and
five-photo validation includes retained images. No other app needs model changes.

## AI Disclosure — Adyra Rachellyn Arkossand

### Module Responsibility

I was responsible for the **Items Management / Catalogue** module in Yelloved. My work covers the Catalogue page, item CRUD flow, item detail, search and filters, pagination, responsive interface, Add/Edit Item form, external catalogue import, and API fallback testing.

### AI Tools Used

I used the following AI tools as development assistants:

- **ChatGPT**
- **Codex**

AI was used as a supporting tool for discussion, drafting, debugging, and reviewing possible approaches. Final implementation choices, testing, commits, and Pull Request integration were completed and checked manually by me.

### Purpose of AI Usage

I used AI to support several development activities:

1. **UI/UX planning**
   - Brainstorming the Catalogue page layout and Item card presentation.
   - Refining the visual consistency between Catalogue and Wanted Board.
   - Designing responsive layouts for desktop and mobile screens.
   - Refining the Add Item form, including rounded input fields, spacing, required markers, and visual hierarchy.
   - Reviewing pagination size, spacing, and behaviour so it matches the Wanted Board design.

2. **Frontend implementation**
   - Drafting and reviewing HTML and CSS for Catalogue-related templates.
   - Improving responsive card grids, search/filter components, loading states, empty states, and pagination.
   - Adjusting the cart notification badge colour so it is visually consistent with the chat notification badge.
   - Creating scoped CSS changes to avoid affecting other modules.

3. **Django and backend understanding**
   - Understanding Django model, form, route, ownership, and validation concepts used in the Items module.
   - Reviewing possible solutions for item CRUD, owner-only edit/delete access, and public JSON data.
   - Understanding migration conflicts after integrating updates from the `main` branch.
   - Understanding local Cloudinary configuration problems and safe local development fallback behaviour.

4. **External API and test support**
   - Discussing the DummyJSON Products API integration for catalogue seed data.
   - Planning fallback behaviour when DummyJSON is unavailable or returns invalid data.
   - Creating and reviewing test scenarios for API failure, invalid JSON, cache-read failure, cache-write failure, and local sample-data fallback.
   - Interpreting automated test results and Django system-check output.

5. **Git and collaboration support**
   - Understanding branch synchronization, Pull Requests, peer review requirements, merge conflicts, and merge commits.
   - Drafting descriptive conventional commit messages and Pull Request summaries.
   - Reviewing which changes should be retained when resolving conflicts between my Catalogue work and the latest `main` branch.

### Prompt Strategy and Scope Control

I did not use broad prompts asking AI to change the whole project. Instead, I included the feature context, technical constraints, and allowed file scope in each request.

For UI tasks, I explicitly instructed AI to limit changes to the Items module, especially files such as:

- `templates/items/explore.html`
- `templates/items/_results.html`
- `templates/items/item_form.html`
- `static/css/explore.css`

For example, when refining the Add Item form, I specified that AI should only improve the required marker and visual styling, while not changing Django validation, models, migrations, backend logic, or the existing form layout and functionality.

For Catalogue styling, I required the result to follow the existing Yelloved design system: purple, cream, and yellow colours; rounded controls; consistency with Wanted Board; and responsive behaviour on smaller screens.

For API-related work, I specified that DummyJSON should be treated as an external source, data should remain appropriate for a student preloved catalogue, and the application should still provide local fallback data if the external API or cache is unavailable.

### Human Review and Manual Validation

Every AI-assisted output was reviewed and adjusted manually before it was used in the project.

The manual validation process included:

- Checking whether suggested changes matched the existing Django project structure.
- Ensuring changes stayed within the Items module and did not unintentionally modify other team members’ modules.
- Reviewing generated HTML/CSS before applying it to existing templates.
- Opening the Catalogue and Add Item pages in a browser to inspect desktop and mobile appearance.
- Manually revising card sizes, grid columns, gaps, responsive spacing, pagination dimensions, border radius, and colour choices when the first output did not match the intended design.
- Checking that only the `*` required marker became red while the rest of the form label remained dark purple.
- Confirming that search, filters, pagination, item creation, item edit, item deletion, and owner-only access still worked after UI updates.
- Running Django checks with `python manage.py check`.
- Running automated tests for the Items and Wanted Board modules, including tests related to DummyJSON fallback and cache failure handling.
- Creating descriptive commits on `feat/items-crud-adyra`.
- Submitting changes through Pull Requests and requesting peer review before merging into `main`.

### Limitations of AI Output

AI output had limitations and was not always suitable for direct use.

Some limitations I encountered were:

- Initial CSS suggestions could make Catalogue pagination, buttons, or form components too large compared with the Wanted Board reference.
- Responsive CSS suggestions could look acceptable on desktop but still be too cramped or incorrectly sized on mobile devices.
- AI could suggest a wider change than necessary, even when the task only required a small visual adjustment.
- AI could assume an outdated repository state after other team members had updated `main`.
- AI could not independently determine which version of a Git conflict should be retained without understanding the latest product decisions.
- AI could explain migration conflicts, but the generated merge migration and resulting project state still had to be checked manually.
- AI-assisted API fallback ideas still required real automated tests to confirm that the application handled unavailable API data, invalid JSON, and unavailable cache safely.

### Manual Fixes Made After AI Assistance

Because of those limitations, I manually performed several corrections:

- Reduced and refined pagination sizing and spacing so it followed the Wanted Board component style.
- Adjusted responsive Catalogue grid behaviour and mobile spacing after browser testing.
- Refined the Add Item form so inputs and selects had softer rounded corners without changing its functionality.
- Changed only the required `*` marker to red while preserving the dark-purple label colour.
- Resolved merge conflicts by retaining the latest Catalogue implementation where appropriate and keeping incoming changes from `main` where they were needed.
- Created and applied migration merge files to resolve conflicting migration leaf nodes.
- Verified local configuration and installed required dependencies after pulling updates from `main`.
- Tested API fallback and cache-failure behaviour using Django automated tests.

### Evidence of Contribution

- **Feature branch:** `feat/items-crud-adyra`
- **Module routes:**
  - `/explore/`
  - `/explore/api/`
  - `/explore/create/`
  - `/explore/<id>/`
  - `/explore/<id>/edit/`
  - `/explore/<id>/delete/`
- **Main contributions:**
  - Item CRUD and owner-only access.
  - AJAX Catalogue search, filters, and pagination.
  - Responsive Catalogue card grid.
  - Add/Edit Item form interface.
  - DummyJSON catalogue import.
  - Local sample-data and cache/API failure fallback testing.
  - Catalogue visual consistency with Wanted Board.
- **Validation performed:**
  - `python manage.py check`
  - `python manage.py test items wanted_board`
- **Pull Requests and commits:** Available in the repository GitHub history under my feature branch and Pull Requests.