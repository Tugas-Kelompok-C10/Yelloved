# Yelloved 🌱

```bash
⁠Proyek Tengah Semester — Mata Kuliah Pemrograman Berbasis Platform (PBP) 
Gasal 2026/2027
Kelas C
Tema: Sustainable Living (Slow Fashion & Conscious Shopping)
```

## Anggota Kelompok

| No. | Nama | NPM |
|:---:|---|:---:|
| 1 | Cindy Olivia Chai | 2506615753 |
| 2 | Muhammad Adib Islami | 2506657030 |
| 3 | Adyra Rachellyn Arkosand | 2506620620 |
| 4 | Baron Rashad Putrajani | 2506623351 |
| 5 | Rizky Dzaky Hamonangan Manihuruk | 2506657301 |

## Deskripsi Aplikasi

Yelloved merupakan platform jual beli dan pertukaran barang preloved yang ditujukan untuk mahasiswa Universitas Indonesia. Pengguna dapat mencari, menjual, bahkan memberikan barang yang masih layak pakai di sekitar lingkungan kampus UI. Yelloved juga menyediakan fitur wanted post untuk membantu pengguna menemukan barang yang sedang mereka butuhkan.

### Value Proposition Questions
- Siapa target pengguna aplikasi ini?
  Mahasiswa aktif Universitas Indonesia dan kampus sekitar Depok, khususnya anak kos dan mahasiswa yang baru wisuda atau pindah kos dan ingin melepas barang-barangnya, serta mahasiswa lain yang mencari barang kebutuhan kuliah/kos dengan harga terjangkau.

- Masalah apa yang mereka hadapi saat ini?
  Barang-barang kos, pakaian, dan alat kuliah yang masih layak pakai sering dibuang begitu saja saat wisuda atau pindah kos karena tidak ada wadah jual-beli yang terorganisir khusus lingkup UI. transaksi biasanya tersebar di story Instagram ataupu grup chat/Line/WhatsApp yang riwayatnya cepat tenggelam dan sulit dicari kembali.

- ⁠Bagaimana aplikasi ini menyelesaikan masalah tersebut?
  Yelloved menyediakan platform terpusat khusus mahasiswa UI dengan fitur Explore Items (pencarian & filter barang) dan Wanted Board (posting kebutuhan barang), sehingga barang preloved lebih mudah ditemukan dan dicocokkan dengan yang membutuhkan.

- Apa manfaat utama yang dirasakan pengguna?
  Penjual bisa melepas barang dengan cepat ke sesama mahasiswa UI tanpa mubazir, sedangkan pembeli hemat biaya dan tidak perlu beli barang baru — sekaligus mengurangi sampah tekstil dan barang kos yang terbuang.

- ⁠Kenapa pengguna akan memilih aplikasi ini dibanding alternatif lain?
  Yelloved fokus khusus pada komunitas UI sehingga transaksi lebih relevan dan dekat secara lokasi (mudah COD sekitar kampus/kos), serta punya fitur Wanted Board yang jarang dimiliki marketplace umum.

### Perbandingan dengan Aplikasi Serupa

| Aplikasi Pembanding | Kelebihan | Kekurangan | Perbedaan dengan Yelloved |
|---|---|---|---|
| Carousell | Basis pengguna besar & lintas kategori (fashion, gadget, perkakas, dll), ada fitur chat dan tawar-menawar harga, mendeteksi lokasi agar bisa COD dengan pengguna terdekat | Cakupan pengguna sangat luas dan umum (tidak spesifik komunitas kampus), sehingga pembeli/penjual bisa dari mana saja dan sulit dipastikan sesama mahasiswa UI | Yelloved membatasi lingkup ke mahasiswa UI saja sehingga lebih relevan, tepercaya, dan lokasinya benar-benar dekat (sekitar kampus/kos) |
| Preloved | Fokus khusus fashion secondhand, ada fitur pembayaran & pengiriman terintegrasi (QRIS, pelacakan paket) sehingga transaksi lebih aman | Hanya mencakup kategori fashion, tidak ada fitur untuk memposting kebutuhan (wanted) barang, dan tidak ada fitur untuk barang non-fashion seperti perlengkapan kos/buku kuliah | Yelloved mencakup barang preloved apa pun yang relevan untuk mahasiswa (bukan cuma fashion) dan punya fitur Wanted Board untuk mencari barang yang dibutuhkan |
| Facebook Marketplace | Basis pengguna besar, mudah diakses karena terintegrasi dengan akun Facebook | Tidak ada filter komunitas kampus, rawan penipuan karena penjual/pembeli acak dan lokasi tersebar luas | Yelloved membatasi lingkup ke mahasiswa UI saja sehingga lebih terpercaya dan lokasinya dekat |

### Tools
- Python
- ⁠Django
- HTML5

## Daftar Modul

| Modul | Deskripsi | PIC |
|-------|-----------|-----|
| Account & Profile | Mengelola akun pengguna mulai dari registrasi, login, logout, hingga informasi profil. Pengguna dapat melengkapi profil dan melihat aktivitas mereka di platform, seperti barang yang pernah diposting, wanted post, serta transaksi yang telah diselesaikan. | Adib |
| Payment & Transaction |  Mengelola proses checkout, pembayaran, dan transaksi barang. Pengguna dapat membuat transaksi, melihat detail dan riwayat transaksi, memperbarui status pembayaran, serta membatalkan transaksi yang masih berjalan. | Dzaky |
| Items Management | Memungkinkan pengguna menawarkan barang yang sudah tidak digunakan tetapi masih layak pakai. Pengguna dapat membuat, mengubah, dan menghapus posting dengan memasukkan informasi barang, foto, kondisi, dan sebagainya. Pemilik juga dapat memperbarui status barang ketika sudah tidak tersedia. | Adyra |
| Wanted Board | Menyediakan ruang bagi pengguna yang sedang mencari barang tertentu untuk membuat wanted post. Pengguna dapat menjelaskan barang yang dibutuhkan dan informasi tambahan lainnya. Pengguna lain yang memiliki barang yang sesuai dapat memberikan penawaran terhadap wanted post tersebut. | Cindy |
| Chat | Percakapan pribadi antar pengguna untuk membahas barang, harga, dan lokasi pertemuan. Pengguna dapat mengirim, mengedit, menghapus pesan, melampirkan file, dan melihat preview percakapan serta badge pesan belum dibaca di navbar. | Cindy |
| Item Matching & Exchange | Menghubungkan pengguna yang memiliki barang dengan pengguna yang sedang membutuhkannya. Pengguna dapat mengajukan request terhadap suatu barang atau menawarkan barang sebagai respons terhadap wanted post. | Baron |

Setiap modul Django memiliki app sendiri: `account_profile`, `transactions`, `items`, `wanted_board`, `item_matching`, dan `chat`. App `home` menangani halaman utama proyek. Semua app terdaftar di `INSTALLED_APPS` pada `home/settings.py`.

## Setup dan Menjalankan Proyek

Instruksi PowerShell berikut dijalankan dari folder repository yang berisi `manage.py`.
Python 3.13 dipakai pada development saat ini. Versi library mengikuti `requirements.txt`

### 1. Clone repository

```
git clone https://github.com/Tugas-Kelompok-C10/Yelloved.git
cd Yelloved
```
### 2. Create virtual environment

Windows:
```
python -m venv env
env\Scripts\activate
```


macOS/Linux:
```
python3 -m venv env
source env/bin/activate
```

### 3. Install dependency

```
pip install -r requirements.txt
```

### 4. Konfigurasi `.env` lokal

Buat file `.env` di folder yang sama dengan `manage.py` isi dengan:

```
PRODUCTION=False
SECRET_KEY=replace-with-a-generated-development-key
```

Generate key dengan command berikut, lalu salin hasilnya ke `SECRET_KEY`:

```
-c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5. Migrasi, akun, dan server

```
python manage.py migrate
python manage.py runserver
```

Buka `http://127.0.0.1:8000/`.

## Sumber Dataset / Public API

- https://dummyjson.com/docs/auth
- https://dummyjson.com/users
- https://dummyjson.com/docs/products
- https://github.com/emsifa/api-wilayah-indonesia.git

## Roles

- User: Pengguna utama yang dapat mencari dan melihat barang, membuat posting barang untuk dijual atau diberikan, serta membuat wanted post untuk mencari barang yang dibutuhkan. User juga dapat melakukan request, menyelesaikan transaksi, dan memberikan rating atau review.
- Admin: Pengelola platform yang bertanggung jawab untuk memantau aktivitas pengguna dan mengelola konten, termasuk mengelola data barang, pengguna, serta menangani laporan atau pelanggaran pada platform.

## Links

- Deployment PWS: https://cindy-olivia-yelloved.pws.cs.ui.ac.id/
- Figma: https://www.figma.com/design/vX59epB4suKi9Hn0AvAlCm/Desktop?m=auto&t=lBfJytlKiMLzHr9P-6

## AI Disclosure

Disclosure ini menjelaskan bantuan AI pada pekerjaan.

### Tools dan tujuan penggunaan

| Tool | Penggunaan dalam pekerjaan ini |
|---|---|
| OpenAI Codex / asisten AI | Membantu membaca repository, menjelaskan alur Django/JavaScript, menyusun dan mengubah kode, meninjau edge case, menulis tes, dan membantu commit terarah |
| Claude Design | Membantu membuat design hi-fi berdasarkan referensi design dan konteks yang diberikan |

### Strategi prompt

#### Cindy
Pekerjaan dipecah menjadi perubahan kecil dengan batas modul yang eksplisit.

1. **Tetapkan konteks:** inspect struktur Models → Forms → Views → Templates → JavaScript sebelum menyimpulkan penyebab masalah.
2. **Tetapkan batas:** hanya sentuh modul yang diizinkan; gunakan `base.html`, CSS global, token `:root`, lebar konten 1280 px, dan copywriting Inggris pada UI.
3. **Minta alur konkret:** misalnya search debounce 300 ms, filter dapat digabung dengan sorting/pagination, atau tombol Chat mengarah ke pemilik Wanted.
4. **Minta kasus negatif:** duplicate submit, dua tab mengedit bersamaan, status post berubah saat offer diproses, session berganti akun, timeout, file tidak valid, serta request bersamaan di batas kuota.
5. **Verifikasi dan koreksi:** jalankan tes, baca error aktual, bandingkan hasil dengan screenshot, lalu lakukan perbaikan terarah dan commit sesuai konteks perubahan.

### Keterbatasan AI, koreksi terarah, dan bukti verifikasi

#### Cindy 
Bantuan AI digunakan untuk menjelaskan dan menuilskan kode backend, frontend, dan tes yang sesuai dengan intstruksi, requirements, dan batasan yang diberikan. AI paling banyak digunakan untuk logika penulisan kode terutama pada backend; 

| Keterbatasan / masalah | Koreksi dan cara memeriksa |
|---|---|
| Styling dapat menyimpang dari desain yang diberikan: warna, ukuran icon, chip, dan spacing tidak selalu tepat pada percobaan pertama. | Saya memberi screenshot dan koreksi; styling direvisi untuk selalu memakai token root dan shared CSS, bukan menerima hasil pertama tanpa review. |
| Jika AI tidak diberikan instruksi yang clear akan mencoba menambahkan hal yang tidak diperlukan| Saya selalu memberikan konteks pekerjaan, poin poin apa saja yang perlu dikerjakan dan tidak perlu dikerjakan, serta reminder untuk tidak menyentuh modul yang bukan milik saya |
