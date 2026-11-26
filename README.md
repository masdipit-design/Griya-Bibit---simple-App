# Griya Bibit Sumber Sari

Aplikasi toko bibit tanaman berbasis terminal (CLI) dengan Python dan PostgreSQL.
Menjual bibit, benih, pupuk, dan nutrisi tanaman. Tersedia tiga peran: Admin, Pegawai Kebun, dan Pelanggan.

## Fitur
- Pelanggan: registrasi, belanja per kategori, keranjang, checkout dengan diskon grosir (2-3%), riwayat transaksi.
- Pegawai kebun: catat pembibitan baru, selesaikan batch (jumlah siap jual dan mati), stok bertambah otomatis.
- Admin: kelola produk dan akun pegawai, lihat pembibitan, laporan penjualan dan stok.
- Checkout memakai transaksi atomik: tersimpan lengkap atau batal semua.

## Cara menjalankan
1. Pasang PostgreSQL dan driver Python:

        pip install psycopg2-binary

2. Buat database di PostgreSQL (misalnya lewat pgAdmin), lalu jalankan file `Griya bibit.sql`
   untuk membuat tabel dan data contoh.
3. Atur koneksi di bagian DB_CONFIG pada file Python, atau lewat variabel lingkungan
   GRIYA_DB_NAME, GRIYA_DB_USER, GRIYA_DB_HOST, GRIYA_DB_PASS.
4. Jalankan aplikasi:

        python griya_bibit.py

## Akun contoh (data fiktif)
| Peran | Username | Password |
|---|---|---|
| Admin | Dapyy@JR | 23571113 |
| Pegawai | cinta_2 | cintanihbos |
| Pelanggan | jerom97 | mathISfun |

## Teknologi
Python 3, PostgreSQL, psycopg2.
