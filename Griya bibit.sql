-- =====================================================================
-- DDL: perubahan dari versi awal agar cocok dengan data INSERT_KHUSUS_almost.xlsx
--  1. Semua kolom id dan FK: INTEGER -> VARCHAR(10) (ID berawalan: PD01, KT01, PG01, B01, TR01, K01, DT01)
--  2. batch_pembibitan.tinggi_cm: NUMERIC(5) -> NUMERIC(5,1) (ada 18.5, 15.2, 15.6)
--  3. Dilonggarkan jadi boleh NULL karena tidak ada di data/alur registrasi:
--     pengguna.nama, kategori.jenis, transaksi.metode_bayar
-- =====================================================================
CREATE TABLE kategori (
    id_kategori VARCHAR(10) PRIMARY KEY,
    nama_kategori VARCHAR(50) UNIQUE NOT NULL,
    jenis VARCHAR(10)
);

CREATE TABLE pengguna (
    id_pengguna VARCHAR(10) PRIMARY KEY,
    nama VARCHAR(100),
    username VARCHAR(30) UNIQUE NOT NULL,
    password_hash VARCHAR(64) NOT NULL,
    role VARCHAR(10) NOT NULL,
    no_hp VARCHAR(15),
    alamat TEXT,
    dibuat_pada TIMESTAMP
);


CREATE TABLE produk (
    id_produk VARCHAR(10) PRIMARY KEY,
    id_kategori VARCHAR(10) NOT NULL,
    nama_produk VARCHAR(50) NOT NULL,
    nama_ilmiah VARCHAR(50),
    merk VARCHAR(50),
    ukuran VARCHAR(50),
    satuan VARCHAR(15) NOT NULL,
    harga NUMERIC(15) NOT NULL,
    stok INTEGER NOT NULL,
    deskripsi TEXT,
    status_aktif CHAR(1),

    FOREIGN KEY (id_kategori) REFERENCES kategori(id_kategori)
);

CREATE TABLE batch_pembibitan (
    id_batch_pembibitan VARCHAR(10) PRIMARY KEY,
    id_produk VARCHAR(10) NOT NULL,
    id_pengguna VARCHAR(10) NOT NULL,
    tanggal_semai DATE NOT NULL,
    jumlah_awal INTEGER NOT NULL,
    jumlah_siap INTEGER NOT NULL,
    jumlah_mati INTEGER NOT NULL,
    tinggi_cm NUMERIC(5,1),
    status VARCHAR(10) NOT NULL,
    catatan TEXT,

    FOREIGN KEY (id_produk) REFERENCES produk(id_produk),
    FOREIGN KEY (id_pengguna) REFERENCES pengguna(id_pengguna)
);

CREATE TABLE keranjang (
    id_keranjang VARCHAR(10) PRIMARY KEY,
    id_pelanggan VARCHAR(10) NOT NULL,
    id_produk VARCHAR(10) NOT NULL,
    jumlah INTEGER NOT NULL,

    FOREIGN KEY (id_pelanggan) REFERENCES pengguna(id_pengguna),
    FOREIGN KEY (id_produk) REFERENCES produk(id_produk)
);

CREATE TABLE transaksi (
    id_transaksi VARCHAR(10) PRIMARY KEY,
    id_pelanggan VARCHAR(10) NOT NULL,
    tanggal_transaksi DATE NOT NULL,
    total_sebelum_diskon NUMERIC(12) NOT NULL,
    diskon_persen NUMERIC(10) NOT NULL,
    total_akhir NUMERIC(12) NOT NULL,
    dicatat_reseller CHAR(1),
    metode_bayar VARCHAR(10),
    status VARCHAR(10) NOT NULL,

    FOREIGN KEY (id_pelanggan) REFERENCES pengguna(id_pengguna)
);

CREATE TABLE detail_transaksi (
    id_detail_transaksi VARCHAR(10) PRIMARY KEY,
    id_transaksi VARCHAR(10) NOT NULL,
    id_produk VARCHAR(10) NOT NULL,
    jumlah INTEGER NOT NULL,
    harga_satuan NUMERIC(12) NOT NULL,
    subtotal NUMERIC(12) NOT NULL,

    FOREIGN KEY (id_transaksi) REFERENCES transaksi(id_transaksi),
    FOREIGN KEY (id_produk) REFERENCES produk(id_produk)
);


-- =====================================================================
-- INSERT DATA. Tanggal bertipe tanggal dipakai apa adanya; tanggal teks bulan/tgl/tahun (m/d/yyyy) diubah ke yyyy-mm-dd.
-- id_pelanggan diisi id pengguna-nya: PL01 = PG05, PL02 = PG06, PL03 = PG07, PL04 = PG04.
-- Urutan insert mengikuti FK: kategori, pengguna, produk, batch, keranjang, transaksi, detail.
-- =====================================================================

INSERT INTO kategori (id_kategori, nama_kategori) VALUES
 ('KT01', 'Bibit Buah'),
 ('KT02', 'Benih Sayur'),
 ('KT03', 'Pupuk'),
 ('KT04', 'Nutrisi Tanaman');

-- Password disimpan SHA-256 hex (Python: hashlib.sha256(pw.encode()).hexdigest()). nama dan alamat dikosongkan.
INSERT INTO pengguna (id_pengguna, username, password_hash, role, no_hp, dibuat_pada) VALUES
 ('PG01', 'Dapyy@JR', '66ff4a4f00b49cc01bdb298cdeee2797e55ee75bf6c13319b27e528832895e53', 'Admin', '6281234567801', '2026-01-10 00:00:00'),
 ('PG02', 'cinta_2', '7c39e76c438a33ce91aea5081880584731aa8a673b8df1d7571893a43d53b56a', 'Pegawai', '6281234567802', '2026-01-11 00:00:00'),
 ('PG03', 'aulia_3', 'e3e14328b073285dcafe7456c8fba423f8a2596d44baefe9347b057d9ae26629', 'Pegawai', '6281234567803', '2026-01-11 00:00:00'),
 ('PG04', 'idaayu_4', '34a67f1b2d95ccf5b2052632950115cf7b3171ccc51d40ac6a3736c8627e5126', 'Pelanggan', '6281234567804', '2026-03-23 00:00:00'),
 ('PG05', 'jerom97', '87bbc304b838a03db6d5eb82cff8b8d93df86d6894f16e57e40b7df2f51083f1', 'Pelanggan', '6281234567812', '2026-04-15 00:00:00'),
 ('PG06', 'deny@caknan', '4904d4a1bda1fd848e14c9bbec67953871011389936f7e221f9db80b86d9e272', 'Pelanggan', '6281335778921', '2026-05-17 00:00:00'),
 ('PG07', 'roby_purba', 'c10d4b23bde8677b9de668524930d7d31d89cce2c26e6a290f3e65042f5b771f', 'Pelanggan', '6281334556778', '2026-02-27 00:00:00');

-- Spasi ganda/akhir dirapikan; ukuran 0 (PD06) disimpan apa adanya sebagai '0'.
INSERT INTO produk (id_produk, id_kategori, nama_produk, merk, ukuran, satuan, harga, stok, status_aktif) VALUES
 ('PD01', 'KT01', 'Bibit mangga', 'Griya Bibit', 'tinggi 35 cm', 'batang', 25000, 124, 'Y'),
 ('PD02', 'KT01', 'Bibit alpukat', 'Griya Bibit', 'tinggi 18,5 cm', 'batang', 30000, 142, 'Y'),
 ('PD03', 'KT02', 'bibit cabai', 'Griya Bibit', 'tinggi 15,2 cm', 'batang', 15000, 45, 'Y'),
 ('PD04', 'KT03', 'Pupuk organik', 'Griya Bibit', '1 kg', 'kemasan', 12000, 45, 'Y'),
 ('PD05', 'KT02', 'Benih jagung', 'Griya Bibit', '6 gr', 'bungkus', 11000, 65, 'Y'),
 ('PD06', 'KT01', 'Bibit jambu', 'Griya Bibit', '0', 'batang', 20000, 0, 'N'),
 ('PD07', 'KT01', 'Bibit durian', 'Griya Bibit', 'tinggi 10 cm', 'batang', 50000, 37, 'Y'),
 ('PD08', 'KT02', 'bibit tomat', 'Griya Bibit', 'tinggi 12 cm', 'batang', 12000, 109, 'Y'),
 ('PD09', 'KT02', 'bibit kangkung', 'Griya Bibit', 'tinggi 10 cm', 'batang', 8000, 100, 'Y'),
 ('PD10', 'KT04', 'ultimate green spray', 'Griya Bibit', '1 kg', 'kemasan', 25000, 10, 'Y');

-- 'jumlah semai' di spreadsheet = jumlah_awal.
INSERT INTO batch_pembibitan (id_batch_pembibitan, id_produk, id_pengguna, tanggal_semai, jumlah_awal, jumlah_siap, jumlah_mati, tinggi_cm, status, catatan) VALUES
 ('B01', 'PD01', 'PG02', '2026-01-25', 100, 80, 20, 35, 'siap', 'siap jual'),
 ('B02', 'PD02', 'PG02', '2026-01-15', 80, 60, 20, 18.5, 'siap', 'siap jual'),
 ('B03', 'PD01', 'PG02', '2026-02-10', 60, 54, 6, 17, 'siap', 'siap jual'),
 ('B04', 'PD06', 'PG02', '2026-02-17', 50, 0, 50, 0, 'mati', 'tidak siap jual'),
 ('B05', 'PD09', 'PG03', '2026-02-13', 45, 40, 5, 13, 'siap', 'siap jual'),
 ('B06', 'PD03', 'PG03', '2026-12-07', 40, 30, 10, 15.2, 'siap', 'siap jual'),
 ('B07', 'PD03', 'PG03', '2026-12-03', 35, 25, 10, 12, 'siap', 'siap jual'),
 ('B08', 'PD08', 'PG03', '2026-02-28', 30, 30, 0, 12, 'siap', 'siap jual'),
 ('B09', 'PD02', 'PG02', '2026-02-28', 85, 82, 3, 15, 'siap', 'siap jual'),
 ('B10', 'PD08', 'PG03', '2026-03-28', 90, 79, 11, 11, 'siap', 'siap jual'),
 ('B11', 'PD07', 'PG02', '2026-04-01', 95, 87, 8, 10, 'siap', 'siap jual'),
 ('B12', 'PD09', 'PG03', '2026-06-04', 110, 100, 10, 15.6, 'siap', 'siap jual');

INSERT INTO keranjang (id_keranjang, id_pelanggan, id_produk, jumlah) VALUES
 ('K01', 'PG05', 'PD01', 10),
 ('K02', 'PG05', 'PD10', 10),
 ('K03', 'PG07', 'PD07', 50),
 ('K04', 'PG04', 'PD03', 10);

INSERT INTO transaksi (id_transaksi, id_pelanggan, tanggal_transaksi, total_sebelum_diskon, diskon_persen, total_akhir, dicatat_reseller, status) VALUES
 ('TR01', 'PG05', '2026-05-02', 250000, 0, 250000, 'N', 'selesai'),
 ('TR02', 'PG05', '2026-06-01', 250000, 0, 250000, 'N', 'selesai'),
 ('TR03', 'PG07', '2026-06-13', 2500000, 3, 2425000, 'Y', 'selesai'),
 ('TR04', 'PG04', '2026-12-27', 150000, 0, 150000, 'N', 'selesai');

INSERT INTO detail_transaksi (id_detail_transaksi, id_transaksi, id_produk, jumlah, harga_satuan, subtotal) VALUES
 ('DT01', 'TR01', 'PD01', 10, 25000, 250000),
 ('DT02', 'TR02', 'PD10', 10, 25000, 250000),
 ('DT03', 'TR03', 'PD07', 50, 50000, 2500000),
 ('DT04', 'TR04', 'PD03', 10, 15000, 150000);


 -- ======== CHECK AFTER ==========

