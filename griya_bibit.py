
import getpass
import hashlib
import os
import re
import sys
from contextlib import contextmanager
from datetime import date, datetime

# ============================ ATUR DULU ============================
DB_CONFIG = {
    "host": os.environ.get("GRIYA_DB_HOST", "localhost"),   # isi None untuk lewat unix socket
    "port": os.environ.get("GRIYA_DB_PORT", "5432"),
    "dbname": os.environ.get("GRIYA_DB_NAME", "GRIYA BIBIT APP"),
    "user": os.environ.get("GRIYA_DB_USER", "postgres"),
    "password": os.environ.get("GRIYA_DB_PASS"),            # kosong -> ditanya saat program jalan
}
SQL_FILE = "Griya bibit.sql"
AMBANG_GROSIR = [(50, 3), (20, 2)]   # (minimal total item, diskon %), urut dari terbesar
STOK_MENIPIS = 20                    # batas stok untuk laporan "stok menipis"
ROLE_KODE = {"A": "Admin", "K": "Pegawai", "P": "Pelanggan"}


# ============================ Rp, garis, waktu dll. (alat bantu) ============================
def rp(n):
    return "Rp " + f"{int(n):,}".replace(",", ".")


def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def tgl(v):
    return v.strftime("%d/%m/%Y") if hasattr(v, "strftime") else str(v)[:10]


def garis(n=60, c="-"):
    print(c * n)


def ask_pass(prompt):
    return getpass.getpass(prompt)


def ask_int(prompt="> Masukkan angka: ", lo=None, hi=None):
    while True:
        s = input(prompt).strip()
        if s.isdigit():
            n = int(s)
            if (lo is None or n >= lo) and (hi is None or n <= hi):
                return n
            print(f"!! angka harus antara {lo} dan {hi}")
        else:
            print("!! masukin nomor yang udah ada....")


def ask_yn(prompt):
    while True:
        s = input(prompt).strip().upper()
        if s in ("Y", "N"):
            return s == "Y"
        print("!! pilih Y kalau iya.. N kalau nggak...")


def tabel(headers, rows):
    rows = [[str(c) for c in r] for r in rows]
    w = [max(len(h), *(len(r[i]) for r in rows)) if rows else len(h) for i, h in enumerate(headers)]
    print("  ".join(h.ljust(w[i]) for i, h in enumerate(headers)))
    garis(sum(w) + 2 * (len(w) - 1))
    for r in rows:
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)))


# ============================ DATABASE ============================
def connect():
    try:
        import psycopg2
    except ImportError:
        sys.exit("psycopg2 belum terpasang. Pasang dulu: pip install psycopg2-binary")
    cfg = dict(DB_CONFIG)
    if cfg["password"] is None:
        cfg["password"] = getpass.getpass(f"Password PostgreSQL untuk user {cfg['user']} : ")
    cfg = {k: v for k, v in cfg.items() if v is not None}
    try:
        conn = psycopg2.connect(**cfg)
    except Exception as e:
        sys.exit(f"Gagal terhubung ke database: {e}\nCek DB_CONFIG di bagian atas file.")
    conn.autocommit = True
    return conn


def fetch(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params or None)
    rows = cur.fetchall()
    cur.close()
    return rows


def run(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params or None)
    n = cur.rowcount
    cur.close()
    return n


@contextmanager
def atomik(conn):
    """Semua perintah di dalam blok ini tersimpan semua, atau batal semua."""
    conn.autocommit = False
    try:
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True


def next_id(conn, prefix, tabel_, kolom):
    """ID berikutnya: prefix + nomor (PD11, TR05, ...)."""
    pola = re.compile(rf"^{prefix}(\d+)$")
    nomor = [int(m.group(1)) for (v,) in fetch(conn, f"SELECT {kolom} FROM {tabel_}")
             if (m := pola.match(v))]
    return f"{prefix}{(max(nomor) if nomor else 0) + 1:02d}"


class StokKurang(Exception):
    pass


def init_db():
    folder = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, SQL_FILE)
    if not os.path.exists(path):
        sys.exit(f"File {SQL_FILE} tidak ditemukan di {folder}")
    conn = connect()
    try:
        with atomik(conn):
            cur = conn.cursor()
            cur.execute(open(path, encoding="utf-8").read())
            cur.close()
        print("Tabel dan data berhasil dibuat.")
    except Exception as e:
        print(f"Gagal menjalankan {SQL_FILE}: {e}\n(Jika tabel sudah ada, tidak perlu --init.)")
    finally:
        conn.close()


# ============================ AKUN ============================
def registrasi(conn):
    print("\n:: itu daftar dulu bray..")
    while True:
        username = input("siapa username lo: ").strip()
        if not re.fullmatch(r"[A-Za-z0-9_@.\-]{3,30}", username):
            print("!! Nama pengguna harus 3-30 karakter, tanpa spasi. Gunakan huruf, angka, _, @, titik, atau tanda hubung.")
        elif fetch(conn, "SELECT 1 FROM pengguna WHERE username=%s", (username,)):
            print("!! nama itu udah dipakai.. ganti.")
        else:
            break
    while True:
        pw = ask_pass("Kata sandi: ")
        if len(pw) < 4:
            print("!! Kata sandi minimal 4 karakter.")
        elif pw != ask_pass("Ulangi kata sandi: "):
            print("!! kok kata sanddi ga sama?.")
        else:
            break
    if not ask_yn(":: kanjut pendaftaran? [Y/N] "):
        print("Pendaftaran dibatalkan.")
        return False
    new_id = next_id(conn, "PG", "pengguna", "id_pengguna")
    run(conn, "INSERT INTO pengguna (id_pengguna, username, password_hash, role, dibuat_pada) "
              "VALUES (%s, %s, %s, 'Pelanggan', %s)", (new_id, username, hash_pw(pw), datetime.now()))
    print("Data disimpan!")
    return True


def login(conn, role):
    print(":: anda login kami tanya")
    for _ in range(3):
        username = input("username : ").strip()
        pw = ask_pass("sandi lo : ")
        r = fetch(conn, "SELECT id_pengguna, username, role FROM pengguna "
                        "WHERE username=%s AND password_hash=%s AND role=%s",
                  (username, hash_pw(pw), role))
        if r:
            print("Berhasil masuk!")
            return {"id": r[0][0], "username": r[0][1], "role": r[0][2]}
        print("!! Nama pengguna, kata sandi, atau peran salah.")
    print("kok gagal mulu?!.")
    return None


def profil(conn, user):
    while True:
        r = fetch(conn, "SELECT username, role, dibuat_pada FROM pengguna WHERE id_pengguna=%s", (user["id"],))[0]
        print("\n:: Informasi akun Anda")
        garis()
        print(f"Nama pengguna : {r[0]}\nKata sandi    : **********\nPeran         : {r[1]}\nDibuat pada   : {tgl(r[2])}")
        garis()
        pilih = input(":: Ketik [usr] kalau mau ganti username, [passwd] buat ganti password, atau [q] untuk keluar:\n> Pilihan: ").strip().lower()
        if pilih == "q": 
            return
        if pilih == "usr":
            if not ask_yn(":: Yakin ganti username?? [Y/N] "):
                continue
            baru = input("> Nama pengguna baru: ").strip()
            if not re.fullmatch(r"[A-Za-z0-9_@.\-]{3,30}", baru):
                print("!! Nama pengguna harus 3-30 karakter, tanpa spasi. Gunakan huruf, angka, _, @, titik, atau tanda hubung.")
            elif fetch(conn, "SELECT 1 FROM pengguna WHERE username=%s", (baru,)):
                print("!! Nama pengguna sudah dipakai.")
            elif ask_yn(f":: Ubah nama pengguna dari {user['username']} menjadi {baru}? [Y/N] "):
                run(conn, "UPDATE pengguna SET username=%s WHERE id_pengguna=%s", (baru, user["id"]))
                user["username"] = baru
                print("Data akun berhasil diperbarui!")
        elif pilih == "passwd":
            if not ask_yn(":: Yakin mau ganti sandi?? [Y/N] "):
                continue
            lama = ask_pass("> Kata sandi saat ini: ")
            if not fetch(conn, "SELECT 1 FROM pengguna WHERE id_pengguna=%s AND password_hash=%s",
                         (user["id"], hash_pw(lama))):
                print("!! salah weh...")
                continue
            baru = ask_pass("> Kata sandi baru: ")
            if len(baru) < 4:
                print("!! Kata sandi minimal 4 karakter.")
            elif ask_yn(":: Yakin ingin menyimpan perubahan? [Y/N] "):
                run(conn, "UPDATE pengguna SET password_hash=%s WHERE id_pengguna=%s", (hash_pw(baru), user["id"]))
                print("Data akun berhasil diperbarui!")
        else:
            print("!! apa itu wok??.")


# ============================ PELANGGAN: KERANJANG ============================
def get_keranjang(conn, uid):
    rows = fetch(conn, "SELECT k.id_keranjang, p.id_produk, p.nama_produk, p.ukuran, k.jumlah, p.harga, p.stok "
                       "FROM keranjang k JOIN produk p ON p.id_produk = k.id_produk "
                       "WHERE k.id_pelanggan=%s ORDER BY k.id_keranjang", (uid,))
    return [(a, b, c, d, int(e), int(f), int(g)) for a, b, c, d, e, f, g in rows]


def show_keranjang(items):
    print("\n:: Isi keranjang belanja Anda")
    tabel(["No.", "Produk", "Ukuran", "Jumlah", "Harga satuan", "Subtotal"],
          [(i, it[2], it[3] or "-", it[4], rp(it[5]), rp(it[4] * it[5])) for i, it in enumerate(items, 1)])
    garis()
    print(f"Jumlah item : {sum(it[4] for it in items)}")
    print(f"Total biaya : {rp(sum(it[4] * it[5] for it in items))}\n")


def pilih_dari(daftar, nama_idx, prompt):
    """Pilih dengan nomor atau nama persis. Q/C = batal. Mengembalikan elemen daftar atau None."""
    while True:
        s = input(prompt).strip()
        if s.lower() in ("q", "c"):
            return None
        if s.isdigit() and 1 <= int(s) <= len(daftar):
            return daftar[int(s) - 1]
        cocok = [d for d in daftar if d[nama_idx].lower() == s.lower()]
        if cocok:
            return cocok[0]
        print("!! Produk tidak ditemukan. Masukkan nomor atau nama produk dengan tepat.")


def pilih_kategori(conn, ada_keranjang):
    kats = fetch(conn, "SELECT id_kategori, nama_kategori FROM kategori ORDER BY id_kategori")
    print("\n:: Pilih kategori produk:\n[0] Batal")
    for i, k in enumerate(kats, 1):
        print(f"[{i}] {k[1]}")
    if ada_keranjang:
        print("[S] Lihat keranjang")
    while True:
        s = input("> Masukkan angka: ").strip()
        if ada_keranjang and s.upper() == "S":
            return "S"
        if s.isdigit() and 0 <= int(s) <= len(kats):
            return None if int(s) == 0 else kats[int(s) - 1]
        print("!! Masukkan nomor yang tersedia.")


def tambah_ke_keranjang(conn, user, p):
    id_p, nama, ukuran, stok, harga = p
    ada = fetch(conn, "SELECT id_keranjang, jumlah FROM keranjang WHERE id_pelanggan=%s AND id_produk=%s",
                (user["id"], id_p))
    sudah = int(ada[0][1]) if ada else 0
    sisa = int(stok) - sudah
    if sisa <= 0:
        print("!! Stok habis atau seluruh stok sudah ada di keranjang.")
        return False
    if not ask_yn(f":: Tambahkan {nama} ke keranjang? [Y/N] "):
        return False
    qty = ask_int(f"> Masukkan jumlah (maksimal {sisa}): ", 1, sisa)
    if ada:
        run(conn, "UPDATE keranjang SET jumlah = jumlah + %s WHERE id_keranjang=%s", (qty, ada[0][0]))
    else:
        run(conn, "INSERT INTO keranjang (id_keranjang, id_pelanggan, id_produk, jumlah) VALUES (%s,%s,%s,%s)",
            (next_id(conn, "K", "keranjang", "id_keranjang"), user["id"], id_p, qty))
    print(f":: {nama} berhasil ditambahkan ke keranjang!")
    return True


def belanja(conn, user):
    """Pilih kategori & produk. Mengembalikan 'keranjang' (user minta lihat keranjang) atau 'batal'."""
    while True:
        ada = bool(get_keranjang(conn, user["id"]))
        kat = pilih_kategori(conn, ada)
        if kat is None:
            return "batal"
        if kat == "S":
            return "keranjang"
        while True:
            prods = fetch(conn, "SELECT id_produk, nama_produk, ukuran, stok, harga FROM produk "
                                "WHERE id_kategori=%s AND status_aktif='Y' ORDER BY id_produk", (kat[0],))
            if not prods:
                print("!! Belum ada produk aktif dalam kategori ini.")
                break
            print(f"\n[{kat[1]}]")
            tabel(["No.", "Produk", "Ukuran", "Stok", "Harga satuan"],
                  [(i, p[1], p[2] or "-", p[3], rp(p[4])) for i, p in enumerate(prods, 1)])
            p = pilih_dari(prods, 1, ":: Masukkan nama produk dengan tepat atau pilih nomornya. Ketik C untuk batal:\n> Pilih produk: ")
            if p is None:
                break
            if tambah_ke_keranjang(conn, user, p):
                if input(":: Ketik S untuk melihat keranjang atau tekan Enter untuk memilih produk lain:\n> Pilihan: ").strip().upper() == "S":
                    return "keranjang"


def ubah_item(conn, items):
    it = pilih_dari(items, 2, ":: Pilih produk yang ingin diubah (nama atau nomor). Ketik Q untuk batal:\n> Pilihan: ")
    if it is None or not ask_yn(":: Yakin ingin melanjutkan? [Y/N] "):
        return
    if it[6] <= 0:
        print("!! Stok produk ini habis. Silakan hapus dari keranjang.")
        return
    qty = ask_int(f"> Masukkan jumlah (maksimal {it[6]}): ", 1, it[6])
    run(conn, "UPDATE keranjang SET jumlah=%s WHERE id_keranjang=%s", (qty, it[0]))
    print("Keranjang berhasil diperbarui!")


def hapus_item(conn, items):
    it = pilih_dari(items, 2, ":: Pilih produk yang ingin dihapus (nama atau nomor). Ketik Q untuk batal:\n> Pilihan: ")
    if it is None or not ask_yn(":: Yakin ingin melanjutkan? [Y/N] "):
        return
    run(conn, "DELETE FROM keranjang WHERE id_keranjang=%s", (it[0],))
    print(f"{it[2]} berhasil dihapus dari keranjang!")


def hitung_diskon(total_item):
    for minimal, persen in AMBANG_GROSIR:
        if total_item >= minimal:
            return persen
    return 0


def cetak_struk(id_tr, user, items, sebelum, diskon, akhir, bayar, kembali, reseller):
    print("\n" + "=" * 60)
    print("   GRIYA BIBIT SUMBER SARI - STRUK".center(60))
    print("=" * 60)
    print(f"Nomor transaksi : {id_tr}      Tanggal : {tgl(date.today())}")
    print(f"Pelanggan     : {user['username']}")
    garis()
    tabel(["Produk", "Jumlah", "Harga", "Subtotal"],
          [(i[2], i[4], rp(i[5]), rp(i[4] * i[5])) for i in items])
    garis()
    print(f"Total sebelum diskon : {rp(sebelum)}")
    print(f"Pelanggan grosir     : {'ya' if reseller else 'tidak'}  (diskon {diskon}%)")
    print(f"Total akhir          : {rp(akhir)}")
    print(f"Pembayaran (tunai)   : {rp(bayar)}")
    print(f"Kembalian            : {rp(kembali)}")
    print("=" * 60)


def checkout(conn, user):
    items = get_keranjang(conn, user["id"])
    if not items:
        print("!! Keranjang masih kosong.")
        return False
    show_keranjang(items)
    kurang = [i for i in items if i[4] > i[6]]
    if kurang:
        print("!! Stok tidak cukup untuk: " + ", ".join(f"{i[2]} (stok {i[6]})" for i in kurang))
        print("   Silakan ubah jumlah atau hapus produk tersebut terlebih dahulu.")
        return False
    if not ask_yn("Yakin ingin melanjutkan transaksi? [Y/N] "):
        return False
    total_item = sum(i[4] for i in items)
    sebelum = sum(i[4] * i[5] for i in items)
    diskon, reseller = 0, "N"
    tawaran = hitung_diskon(total_item)
    if tawaran:
        print(f"\n** Kamu membeli {total_item} item. Jika dicatat sebagai pelanggan grosir, semua produk di keranjang mendapat diskon {tawaran}% **")
        if ask_yn(":: Catat sebagai pelanggan grosir? [Y/N] "):
            diskon, reseller = tawaran, "Y"
    akhir = (sebelum * (100 - diskon) + 50) // 100
    print(f"\nTotal sebelum diskon : {rp(sebelum)}\nDiskon               : {diskon}%\nTotal yang dibayar   : {rp(akhir)}")
    if input("\n:: Untuk konfirmasi, masukkan kembali nama pengguna Anda:\n> Nama pengguna: ").strip() != user["username"]:
        print("!! Nama pengguna tidak cocok. Transaksi dibatalkan.")
        return False
    while True:
        s = input(f"> Masukkan uang pembayaran (minimal {rp(akhir)}), atau Q untuk batal: ").strip()
        if s.lower() == "q":
            return False
        if s.isdigit() and int(s) >= akhir:
            bayar = int(s)
            break
        print("!! Jumlah pembayaran kurang atau bukan angka.")
    try:
        id_tr = next_id(conn, "TR", "transaksi", "id_transaksi")
        with atomik(conn):       # semua langkah di bawah tersimpan lengkap atau batal semua
            for (_, id_p, nama, _, jml, _, _) in items:
                n = run(conn, "UPDATE produk SET stok = stok - %s WHERE id_produk=%s AND stok >= %s AND status_aktif='Y'",
                        (jml, id_p, jml))
                if n != 1:
                    raise StokKurang(nama)
            run(conn, "INSERT INTO transaksi (id_transaksi, id_pelanggan, tanggal_transaksi, total_sebelum_diskon, "
                      "diskon_persen, total_akhir, dicatat_reseller, metode_bayar, status) "
                      "VALUES (%s,%s,%s,%s,%s,%s,%s,'tunai','selesai')",
                (id_tr, user["id"], date.today(), sebelum, diskon, akhir, reseller))
            for (_, id_p, _, _, jml, harga, _) in items:
                run(conn, "INSERT INTO detail_transaksi (id_detail_transaksi, id_transaksi, id_produk, jumlah, "
                          "harga_satuan, subtotal) VALUES (%s,%s,%s,%s,%s,%s)",
                    (next_id(conn, "DT", "detail_transaksi", "id_detail_transaksi"), id_tr, id_p, jml, harga, jml * harga))
            run(conn, "DELETE FROM keranjang WHERE id_pelanggan=%s", (user["id"],))
    except StokKurang as e:
        print(f"!! stok {e} baru saja tidak cukup. Transaksi dibatalkan, keranjangmu tetap tersimpan.")
        return False
    cetak_struk(id_tr, user, items, sebelum, diskon, akhir, bayar, bayar - akhir, reseller == "Y")
    print("Transaksi berhasil! Anda akan kembali ke menu utama.")
    return True


def menu_keranjang(conn, user):
    """Mengembalikan 'logout' jika user memilih logout, selain itu None."""
    while True:
        items = get_keranjang(conn, user["id"])
        if not items:
            print(":: Keranjang kosong.")
            return None
        show_keranjang(items)
        print(":: Pilih tindakan untuk keranjang Anda:\n"
              "[0] Kosongkan keranjang\n[1] Tambah produk\n[2] Ubah jumlah produk\n"
              "[3] Hapus produk\n[4] Buat transaksi\n[5] Keluar (keranjang tetap tersimpan)")
        pilih = ask_int(lo=0, hi=5)
        if pilih == 0:
            if ask_yn(":: hapus SEMUA isi keranjang? [Y/N] "):
                run(conn, "DELETE FROM keranjang WHERE id_pelanggan=%s", (user["id"],))
                print("Keranjang berhasil dikosongkan. Kembali ke menu utama.")
                return None
        elif pilih == 1:
            belanja(conn, user)
        elif pilih == 2:
            ubah_item(conn, items)
        elif pilih == 3:
            hapus_item(conn, items)
        elif pilih == 4:
            if checkout(conn, user):
                return None
        else:
            return "logout"


def riwayat(conn, user):
    trs = fetch(conn, "SELECT id_transaksi, tanggal_transaksi, total_sebelum_diskon, diskon_persen, total_akhir, "
                      "dicatat_reseller FROM transaksi WHERE id_pelanggan=%s "
                      "ORDER BY tanggal_transaksi DESC, id_transaksi DESC", (user["id"],))
    print("\n:: Riwayat transaksi Anda")
    if not trs:
        print("(Belum ada transaksi.)")
        return
    for t in trs:
        garis(60, "=")
        print(f"{t[0]}   Tanggal: {tgl(t[1])}   Pelanggan grosir: {'ya' if t[5] == 'Y' else 'tidak'}   Diskon: {int(t[3])}%")
        det = fetch(conn, "SELECT p.nama_produk, d.jumlah, d.harga_satuan, d.subtotal FROM detail_transaksi d "
                          "JOIN produk p ON p.id_produk=d.id_produk WHERE d.id_transaksi=%s ORDER BY d.id_detail_transaksi", (t[0],))
        tabel(["Produk", "Jumlah", "Harga satuan", "Subtotal"], [(a, b, rp(c), rp(d)) for a, b, c, d in det])
        print(f"Total sebelum diskon: {rp(t[2])}   total sesudah: {rp(t[4])}")


def menu_pelanggan(conn, user):
    while True:
        print("\n:: Apa yang ingin Anda lakukan?\n[0] Keluar\n[1] Belanja produk\n[2] Lihat riwayat transaksi\n[3] Lihat profil")
        pilih = ask_int(lo=0, hi=3)
        if pilih == 0:
            return
        if pilih == 1:
            hasil = belanja(conn, user)
            if hasil == "keranjang" and menu_keranjang(conn, user) == "logout":
                return
        elif pilih == 2:
            riwayat(conn, user)
        else:
            profil(conn, user)


# ============================ PEGAWAI KEBUN ============================
SQL_BIBIT = "LOWER(SUBSTR(nama_produk, 1, 5)) = 'bibit'"      # produk bibit = nama diawali "bibit"


def lihat_batch(conn):
    rows = fetch(conn, "SELECT b.id_batch_pembibitan, p.nama_produk, b.tanggal_semai, b.jumlah_awal, b.jumlah_siap, "
                       "b.jumlah_mati, b.tinggi_cm, b.status, u.username FROM batch_pembibitan b "
                       "JOIN produk p ON p.id_produk=b.id_produk JOIN pengguna u ON u.id_pengguna=b.id_pengguna "
                       "ORDER BY b.tanggal_semai DESC, b.id_batch_pembibitan DESC")
    print("\nDaftar Pembibitan")
    tabel(["Kode batch", "Produk", "Tanggal semai", "Jumlah awal", "Siap jual", "Mati", "Tinggi", "Status", "Pegawai"],
          [(r[0], r[1], tgl(r[2]), r[3], r[4], r[5], f"{float(r[6]):g} cm" if r[6] is not None else "-", r[7], r[8]) for r in rows])


def batch_baru(conn, user):
    prods = fetch(conn, f"SELECT id_produk, nama_produk, ukuran FROM produk WHERE {SQL_BIBIT} AND status_aktif='Y' ORDER BY id_produk")
    if not prods:
        print("!! Belum ada produk bibit yang aktif.")
        return
    tabel(["No.", "Produk", "Ukuran"], [(i, p[1], p[2] or "-") for i, p in enumerate(prods, 1)])
    p = pilih_dari(prods, 1, ":: Pilih produk bibit (nomor atau nama produk). Ketik Q untuk batal:\n> Pilihan: ")
    if p is None:
        return
    while True:
        s = input("> Tanggal semai (YYYY-MM-DD, Enter = hari ini): ").strip()
        try:
            tanggal = date.today() if not s else datetime.strptime(s, "%Y-%m-%d").date()
            break
        except ValueError:
            print("!! Format tanggal tidak valid. Gunakan YYYY-MM-DD.")
    awal = ask_int("> Jumlah bibit yang disemai: ", 1)
    while True:
        s = input("> Tinggi awal (cm, Enter = 0): ").strip().replace(",", ".")
        try:
            tinggi = float(s) if s else 0.0
            if 0 <= tinggi < 1000:
                break
        except ValueError:
            pass
        print("!! Masukkan angka yang valid, contoh: 12.5.")
    if not ask_yn(f":: Simpan pembibitan {p[1]} ({awal} bibit)? [Y/N] "):
        return
    id_b = next_id(conn, "B", "batch_pembibitan", "id_batch_pembibitan")
    run(conn, "INSERT INTO batch_pembibitan (id_batch_pembibitan, id_produk, id_pengguna, tanggal_semai, jumlah_awal, "
              "jumlah_siap, jumlah_mati, tinggi_cm, status, catatan) VALUES (%s,%s,%s,%s,%s,0,0,%s,'tumbuh','sedang dirawat')",
        (id_b, p[0], user["id"], tanggal, awal, tinggi))
    print(f"Pembibitan {id_b} berhasil disimpan. Status: tumbuh.")


def selesaikan_batch(conn):
    rows = fetch(conn, "SELECT b.id_batch_pembibitan, p.nama_produk, b.tanggal_semai, b.jumlah_awal, p.id_produk "
                       "FROM batch_pembibitan b JOIN produk p ON p.id_produk=b.id_produk "
                       "WHERE b.status='tumbuh' ORDER BY b.id_batch_pembibitan")
    if not rows:
        print("(Tidak ada pembibitan yang sedang tumbuh.)")
        return
    tabel(["No.", "Kode batch", "Produk", "Tanggal semai", "Jumlah awal"], [(i, r[0], r[1], tgl(r[2]), r[3]) for i, r in enumerate(rows, 1)])
    b = pilih_dari(rows, 0, ":: Pilih pembibitan (nomor atau kode batch). Ketik Q untuk batal:\n> Pilihan: ")
    if b is None:
        return
    awal = int(b[3])
    siap = ask_int(f"> Jumlah bibit siap jual (0-{awal}): ", 0, awal)
    mati = ask_int(f"> Jumlah bibit mati (0-{awal - siap}): ", 0, awal - siap)
    s = input("> Tinggi akhir (cm, Enter = tidak diubah): ").strip().replace(",", ".")
    tinggi = None
    if s:
        try:
            tinggi = float(s)
        except ValueError:
            print("!! Tinggi tidak valid, perubahan tinggi diabaikan.")
    status, catatan = ("siap", "siap jual") if siap > 0 else ("mati", "tidak siap jual")
    if not ask_yn(f":: batch {b[0]}: siap {siap}, mati {mati}, status '{status}'. Simpan? [Y/N] "):
        return
    with atomik(conn):
        run(conn, "UPDATE batch_pembibitan SET jumlah_siap=%s, jumlah_mati=%s, status=%s, catatan=%s WHERE id_batch_pembibitan=%s",
            (siap, mati, status, catatan, b[0]))
        if tinggi is not None:
            run(conn, "UPDATE batch_pembibitan SET tinggi_cm=%s WHERE id_batch_pembibitan=%s", (tinggi, b[0]))
        if siap > 0:
            run(conn, "UPDATE produk SET stok = stok + %s WHERE id_produk=%s", (siap, b[4]))
    print(f"Pembibitan {b[0]} selesai." + (f" Stok {b[1]} bertambah {siap}." if siap else ""))


def menu_pegawai(conn, user):
    while True:
        print("\n:: Menu Pegawai Kebun\n[0] Keluar\n[1] Catat pembibitan baru\n[2] Lihat semua pembibitan\n"
              "[3] Selesaikan pembibitan (jumlah siap jual dan mati)\n[4] Lihat profil")
        pilih = ask_int(lo=0, hi=4)
        if pilih == 0:
            return
        {1: lambda: batch_baru(conn, user), 2: lambda: lihat_batch(conn),
         3: lambda: selesaikan_batch(conn), 4: lambda: profil(conn, user)}[pilih]()


# ============================ ADMIN ============================
def daftar_produk(conn):
    rows = fetch(conn, "SELECT p.id_produk, p.nama_produk, k.nama_kategori, p.ukuran, p.harga, p.stok, p.status_aktif "
                       "FROM produk p JOIN kategori k ON k.id_kategori=p.id_kategori ORDER BY p.id_produk")
    print("\nDaftar produk")
    tabel(["No.", "ID", "Produk", "Kategori", "Ukuran", "Harga", "Stok", "Status"],
          [(i, r[0], r[1], r[2], r[3] or "-", rp(r[4]), r[5], r[6]) for i, r in enumerate(rows, 1)])
    return rows


def produk_baru(conn):
    kats = fetch(conn, "SELECT id_kategori, nama_kategori FROM kategori ORDER BY id_kategori")
    for i, k in enumerate(kats, 1):
        print(f"[{i}] {k[1]}")
    kat = kats[ask_int("> pilih kategori : ", 1, len(kats)) - 1]
    nama = input("> Nama produk: ").strip()
    if not nama or len(nama) > 50:
        print("!! Nama produk wajib diisi dan maksimal 50 karakter.")
        return
    merk = input("> Merek (Enter = Griya Bibit): ").strip() or "Griya Bibit"
    ukuran = input("> Ukuran (contoh: tinggi 30 cm / 1 kg): ").strip()
    satuan = input("> Satuan (batang/kemasan/bungkus/...): ").strip()
    if not satuan:
        print("!! Satuan wajib diisi.")
        return
    harga = ask_int("> Harga satuan (Rp): ", 1)
    stok = ask_int("> Stok awal: ", 0)
    if ask_yn(f":: simpan produk {nama} ({rp(harga)})? [Y/N] "):
        new_id = next_id(conn, "PD", "produk", "id_produk")
        run(conn, "INSERT INTO produk (id_produk, id_kategori, nama_produk, merk, ukuran, satuan, harga, stok, status_aktif) "
                  "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Y')", (new_id, kat[0], nama, merk, ukuran or None, satuan, harga, stok))
        print(f"Produk {new_id} berhasil disimpan.")


def ubah_produk(conn, mode):
    rows = daftar_produk(conn)
    p = pilih_dari(rows, 1, ":: Pilih produk (nomor atau nama produk). Ketik Q untuk batal:\n> Pilihan: ")
    if p is None:
        return
    if mode == "harga":
        h = ask_int(f"> harga baru untuk {p[1]} (sekarang {rp(p[4])}) : ", 1)
        if ask_yn(":: Yakin ingin melanjutkan? [Y/N] "):
            run(conn, "UPDATE produk SET harga=%s WHERE id_produk=%s", (h, p[0]))
            print("Harga berhasil diperbarui.")
    elif mode == "stok":
        t = ask_int(f"> tambahan stok untuk {p[1]} (sekarang {p[5]}) : ", 1)
        if ask_yn(":: Yakin ingin melanjutkan? [Y/N] "):
            run(conn, "UPDATE produk SET stok = stok + %s WHERE id_produk=%s", (t, p[0]))
            print("Stok berhasil diperbarui.")
    else:
        baru = "N" if p[6] == "Y" else "Y"
        if ask_yn(f":: ubah status {p[1]} menjadi {'AKTIF' if baru == 'Y' else 'NONAKTIF'}? [Y/N] "):
            run(conn, "UPDATE produk SET status_aktif=%s WHERE id_produk=%s", (baru, p[0]))
            print("Status produk berhasil diperbarui.")


def menu_produk(conn):
    while True:
        print("\n:: Kelola Produk\n[0] Kembali\n[1] Lihat semua produk\n[2] Tambah produk\n"
              "[3] Ubah harga\n[4] Tambah stok\n[5] Aktifkan/nonaktifkan produk")
        pilih = ask_int(lo=0, hi=5)
        if pilih == 0:
            return
        {1: lambda: daftar_produk(conn), 2: lambda: produk_baru(conn), 3: lambda: ubah_produk(conn, "harga"),
         4: lambda: ubah_produk(conn, "stok"), 5: lambda: ubah_produk(conn, "status")}[pilih]()


def menu_pegawai_admin(conn):
    while True:
        print("\n:: Kelola Akun Pegawai\n[0] Kembali\n[1] Lihat daftar pegawai\n[2] Tambah pegawai")
        pilih = ask_int(lo=0, hi=2)
        if pilih == 0:
            return
        if pilih == 1:
            rows = fetch(conn, "SELECT id_pengguna, username, nama, no_hp, dibuat_pada FROM pengguna "
                               "WHERE role='Pegawai' ORDER BY id_pengguna")
            tabel(["ID", "Nama pengguna", "Nama", "No HP", "Dibuat"], [(r[0], r[1], r[2] or "-", r[3] or "-", tgl(r[4])) for r in rows])
        else:
            while True:
                u = input("> Nama pengguna pegawai: ").strip()
                if not re.fullmatch(r"[A-Za-z0-9_@.\-]{3,30}", u):
                    print("!! Nama pengguna harus 3-30 karakter, tanpa spasi. Gunakan huruf, angka, _, @, titik, atau tanda hubung.")
                elif fetch(conn, "SELECT 1 FROM pengguna WHERE username=%s", (u,)):
                    print("!! Nama pengguna sudah dipakai.")
                else:
                    break
            pw = ask_pass("> Kata sandi (minimal 4 karakter): ")
            if len(pw) < 4:
                print("!! Kata sandi terlalu pendek.")
                continue
            nama = input("> Nama pegawai (Enter = kosong): ").strip() or None
            if ask_yn(f":: Simpan akun pegawai {u}? [Y/N] "):
                run(conn, "INSERT INTO pengguna (id_pengguna, nama, username, password_hash, role, dibuat_pada) "
                          "VALUES (%s,%s,%s,%s,'Pegawai',%s)",
                    (next_id(conn, "PG", "pengguna", "id_pengguna"), nama, u, hash_pw(pw), datetime.now()))
                print("Akun pegawai berhasil disimpan.")


def menu_laporan(conn):
    while True:
        print("\n:: Laporan Toko\n[0] Kembali\n[1] Semua transaksi\n[2] Produk terlaris\n[3] Stok menipis\n[4] Penggunaan diskon grosir")
        pilih = ask_int(lo=0, hi=4)
        if pilih == 0:
            return
        if pilih == 1:
            rows = fetch(conn, "SELECT t.id_transaksi, t.tanggal_transaksi, u.username, t.total_sebelum_diskon, "
                               "t.diskon_persen, t.total_akhir, t.dicatat_reseller FROM transaksi t "
                               "JOIN pengguna u ON u.id_pengguna=t.id_pelanggan ORDER BY t.tanggal_transaksi DESC, t.id_transaksi DESC")
            tabel(["ID", "Tanggal", "Pelanggan", "Sebelum", "Diskon", "Akhir", "Reseller"],
                  [(r[0], tgl(r[1]), r[2], rp(r[3]), f"{int(r[4])}%", rp(r[5]), r[6]) for r in rows])
            omzet = fetch(conn, "SELECT COALESCE(SUM(total_akhir),0) FROM transaksi WHERE status='selesai'")[0][0]
            print(f"\nTotal omzet: {rp(omzet)}  ({len(rows)} transaksi)")
        elif pilih == 2:
            rows = fetch(conn, "SELECT p.nama_produk, SUM(d.jumlah) AS terjual, SUM(d.subtotal) AS omzet FROM detail_transaksi d "
                               "JOIN produk p ON p.id_produk=d.id_produk GROUP BY p.id_produk, p.nama_produk "
                               "ORDER BY terjual DESC, p.nama_produk")
            tabel(["Produk", "Terjual", "Omzet"], [(r[0], int(r[1]), rp(r[2])) for r in rows])
        elif pilih == 3:
            rows = fetch(conn, "SELECT nama_produk, stok, satuan FROM produk WHERE status_aktif='Y' AND stok <= %s "
                               "ORDER BY stok, nama_produk", (STOK_MENIPIS,))
            print(f"Produk aktif dengan stok <= {STOK_MENIPIS}")
            tabel(["Produk", "Stok", "Satuan"], rows)
        else:
            n, potongan = fetch(conn, "SELECT COUNT(*), COALESCE(SUM(total_sebelum_diskon - total_akhir),0) "
                                      "FROM transaksi WHERE diskon_persen > 0")[0]
            print(f"Transaksi dengan diskon grosir: {n}\nTotal potongan harga          : {rp(potongan)}")


def menu_admin(conn, user):
    while True:
        print("\n:: Menu Admin\n[0] Keluar\n[1] Kelola produk\n[2] Kelola akun pegawai\n"
              "[3] Lihat pembibitan\n[4] Lihat laporan\n[5] Lihat profil")
        pilih = ask_int(lo=0, hi=5)
        if pilih == 0:
            return
        {1: lambda: menu_produk(conn), 2: lambda: menu_pegawai_admin(conn), 3: lambda: lihat_batch(conn),
         4: lambda: menu_laporan(conn), 5: lambda: profil(conn, user)}[pilih]()


# ============================ PROGRAM UTAMA ============================
def banner():
    print("=" * 60)
    print("GRIYA BIBIT SUMBER SARI".center(60))
    print("=" * 60)
    print("Selamat datang di Griya Bibit Sumber Sari, toko bibit tanaman Anda.")


def main():
    if "--init" in sys.argv:
        return init_db()
    conn = connect()
    banner()
    menus = {"Admin": menu_admin, "Pegawai": menu_pegawai, "Pelanggan": menu_pelanggan}
    try:
        while True:
            print("\n:: Selamat datang! Silakan pilih langkah berikutnya.")
            jawab = input("Ketik Y untuk daftar, N untuk masuk, atau Q untuk keluar:\n> Pilihan: ").strip().upper()
            try:
                if jawab == "Q":
                    break
                if jawab == "Y":
                    if not registrasi(conn):
                        continue
                    role = "Pelanggan"
                elif jawab == "N":
                    kode = input(":: Pilih jenis akun: A [Admin], K [Pegawai Kebun], P [Pelanggan]:\n> Pilihan: ").strip().upper()
                    if kode not in ROLE_KODE:
                        print("!! Jenis akun tidak dikenal.")
                        continue
                    role = ROLE_KODE[kode]
                else:
                    print("!! Masukkan Y, N, atau Q.")
                    continue
                user = login(conn, role)
                if user:
                    menus[role](conn, user)
                    print("\nAnda berhasil keluar. Terima kasih!")
            except (KeyboardInterrupt, EOFError):
                raise
            except Exception as e:
                print(f"\n!! Terjadi kesalahan: {e}\nKembali ke menu awal.")
    except (KeyboardInterrupt, EOFError):
        print("\nProgram dihentikan.")
    finally:
        conn.close()
    print("Sampai jumpa kembali!")


if __name__ == "__main__":
    main()
