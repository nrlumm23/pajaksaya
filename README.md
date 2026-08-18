# PajakSaya

Aplikasi web pribadi untuk mencatat dan menghitung estimasi SPT Tahunan Pajak Penghasilan Orang Pribadi (versi Coretax PER-11/PJ/2025) — penghasilan pekerjaan, penghasilan final, penghasilan bukan objek pajak, zakat, utang, tanggungan, dan harta.

Aplikasi ini **bukan** produk resmi Direktorat Jenderal Pajak (DJP) dan tidak terhubung ke Coretax — hasil hitungannya hanya alat bantu pribadi untuk mempermudah pengisian SPT di Coretax, bukan pengganti pelaporan resmi.

## Cara install

Butuh [Python 3.9+](https://www.python.org/downloads/) sudah terpasang di komputer.

```bash
pip install -r requirements.txt
```

## Cara jalankan

```bash
python pajak_ku.py
```

Lalu buka `http://127.0.0.1:5000` di browser. Database SQLite (`pajak_pribadi.db`) akan otomatis dibuat kosong di folder yang sama saat pertama kali dijalankan.

## Fitur

- Pencatatan penghasilan pekerjaan (dari bukti potong 1721-A1), penghasilan final, penghasilan bukan objek pajak, dan zakat
- Pencatatan utang, tanggungan, dan harta (kas, piutang, investasi, harta bergerak/tidak bergerak/lainnya)
- Perhitungan otomatis PTKP, biaya jabatan, PKP, dan estimasi PPh terutang (tarif progresif sesuai UU HPP)
- Salin data harta/utang/tanggungan dari tahun pajak sebelumnya
- Review checklist kelengkapan & rekonsiliasi kekayaan antar tahun
- Export ringkasan data ke PDF untuk mempermudah transkrip ke Coretax
- Asisten klasifikasi "Tanya" — cari kategori pajak yang tepat untuk suatu transaksi (basis pengetahuan dari sumber-sumber publik DJP/Ortax/DDTC, bukan nasihat pajak resmi)

## Catatan

Data tersimpan lokal di file SQLite (`pajak_pribadi.db`) yang otomatis diabaikan oleh git (lihat `.gitignore`) — jangan pernah commit file `.db` ini kalau berisi data pribadi.
