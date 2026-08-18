from flask import Flask, request, jsonify, Response
import sqlite3
from datetime import datetime
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect('pajak_pribadi.db')
    conn.row_factory = sqlite3.Row
    return conn

def migrate_db(conn):
    cols_tanggungan = {r[1] for r in conn.execute('PRAGMA table_info(tanggungan)').fetchall()}
    if cols_tanggungan and 'pekerjaan' not in cols_tanggungan:
        conn.execute('ALTER TABLE tanggungan ADD COLUMN pekerjaan TEXT')
    cols_utang = {r[1] for r in conn.execute('PRAGMA table_info(utang)').fetchall()}
    if cols_utang and 'tahun_peminjaman' not in cols_utang:
        conn.execute('ALTER TABLE utang ADD COLUMN tahun_peminjaman INTEGER')

    # Kolom "Informasi Tambahan" bebas isi, ditambahkan ke hampir semua tabel supaya
    # ada tempat mencatat detail yang tidak tercakup kolom baku (menyesuaikan formulir Coretax).
    tabel_info_tambahan = ['penghasilan_pekerjaan', 'utang', 'tanggungan', 'harta_kas',
        'harta_piutang', 'harta_investasi', 'harta_bergerak', 'harta_tidak_bergerak',
        'penghasilan_final', 'penghasilan_bukan_objek']
    for t in tabel_info_tambahan:
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info({t})').fetchall()}
        if cols and 'informasi_tambahan' not in cols:
            conn.execute(f'ALTER TABLE {t} ADD COLUMN informasi_tambahan TEXT')

    cols_lainnya = {r[1] for r in conn.execute('PRAGMA table_info(harta_lainnya)').fetchall()}
    if cols_lainnya and 'bukti_kepemilikan' not in cols_lainnya:
        conn.execute('ALTER TABLE harta_lainnya ADD COLUMN bukti_kepemilikan TEXT')

def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS wp_identitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nik TEXT, npwp TEXT, nama TEXT, telepon TEXT, email TEXT,
            status_kawin TEXT, ptkp_status TEXT)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS penghasilan_pekerjaan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_pemberi TEXT, npwp_pemberi TEXT,
            penghasilan_bruto INTEGER, biaya_jabatan INTEGER,
            penghasilan_neto INTEGER, pph_dipotong INTEGER DEFAULT 0,
            informasi_tambahan TEXT,
            tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS utang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            nama_kreditor TEXT, identitas_kreditor TEXT,
            negara_kreditor TEXT, tahun_peminjaman INTEGER,
            jumlah INTEGER, informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS tanggungan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT, nik TEXT, tanggal_lahir TEXT,
            hubungan TEXT, pekerjaan TEXT, informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS harta_kas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            nama_bank TEXT, no_rekening TEXT,
            lokasi TEXT, pemilik TEXT,
            saldo INTEGER, informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS harta_piutang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            nama_penerima TEXT, lokasi_penerima TEXT,
            identitas_penerima TEXT, tahun_mulai INTEGER,
            nilai_piutang INTEGER, saldo_piutang INTEGER,
            informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS harta_investasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            negara TEXT, nama_institusi TEXT,
            npwp_institusi TEXT, no_akun TEXT,
            tahun_perolehan INTEGER, harga_perolehan INTEGER,
            nilai_saat_ini INTEGER, informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS harta_bergerak (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            merk TEXT, no_polisi TEXT,
            kepemilikan TEXT, tahun_perolehan INTEGER,
            harga_perolehan INTEGER, nilai_saat_ini INTEGER,
            informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS harta_tidak_bergerak (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            lokasi TEXT, luas_tanah INTEGER,
            luas_bangunan INTEGER, tahun_perolehan INTEGER,
            harga_perolehan INTEGER, nilai_saat_ini INTEGER,
            sertifikat TEXT, informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS harta_lainnya (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            tahun_perolehan INTEGER, bukti_kepemilikan TEXT, harga_perolehan INTEGER,
            nilai_saat_ini INTEGER, keterangan TEXT,
            tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS penghasilan_final (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            jumlah_bruto INTEGER, pph_final INTEGER,
            informasi_tambahan TEXT, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS penghasilan_bukan_objek (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT, deskripsi TEXT,
            jumlah INTEGER, informasi_tambahan TEXT,
            tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS zakat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deskripsi TEXT, lembaga TEXT,
            jumlah INTEGER, tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        conn.execute('''CREATE TABLE IF NOT EXISTS catatan_penghasilan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT, deskripsi TEXT, perkiraan_jumlah INTEGER,
            kategori TEXT, status TEXT DEFAULT 'belum', keterangan TEXT,
            tahun INTEGER,
            tanggal_input TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        migrate_db(conn)

        cek = conn.execute('SELECT COUNT(*) as total FROM wp_identitas').fetchone()
        if cek['total'] == 0:
            conn.execute('''INSERT INTO wp_identitas
                (nik, npwp, nama, telepon, email, status_kawin, ptkp_status)
                VALUES (?,?,?,?,?,?,?)''',
                ('','','','','','TK','TK/0'))
        conn.commit()
init_db()

BULAN_ID = ['', 'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']

def tanggal_indonesia(dt):
    return f'{dt.day} {BULAN_ID[dt.month]} {dt.year}'

def get_ptkp(status):
    ptkp_map = {
        'TK/0': 54000000, 'TK/1': 58500000, 'TK/2': 63000000, 'TK/3': 67500000,
        'K/0': 58500000, 'K/1': 63000000, 'K/2': 67500000, 'K/3': 72000000
    }
    return ptkp_map.get(status, 54000000)

def hitung_pph(penghasilan_neto_setahun, ptkp):
    pkp = max(0, penghasilan_neto_setahun - ptkp)
    if pkp <= 60000000:
        return int(pkp * 0.05)
    elif pkp <= 250000000:
        return int(60000000 * 0.05 + (pkp - 60000000) * 0.15)
    elif pkp <= 500000000:
        return int(60000000 * 0.05 + 190000000 * 0.15 + (pkp - 250000000) * 0.25)
    elif pkp <= 5000000000:
        return int(60000000 * 0.05 + 190000000 * 0.15 + 250000000 * 0.25 + (pkp - 500000000) * 0.30)
    else:
        return int(60000000 * 0.05 + 190000000 * 0.15 + 250000000 * 0.25 + 4500000000 * 0.30 + (pkp - 5000000000) * 0.35)

def _compute_pekerjaan(values):
    bruto = values['penghasilan_bruto']
    biaya = min(int(bruto * 0.05), 6000000)
    values['biaya_jabatan'] = biaya
    values['penghasilan_neto'] = bruto - biaya
    return values

def _compute_catatan(values):
    if not values.get('status'):
        values['status'] = 'belum'
    return values

# Setiap entri hanya berisi kolom yang boleh ditulis lewat API - dipakai sebagai
# whitelist nama tabel/kolom sehingga /api/item/<tabel> tidak bisa menyasar tabel lain.
TABLE_SPEC = {
    'penghasilan_pekerjaan': {
        'columns': ['nama_pemberi', 'npwp_pemberi', 'penghasilan_bruto', 'biaya_jabatan',
                    'penghasilan_neto', 'pph_dipotong', 'informasi_tambahan', 'tahun'],
        'int_columns': {'penghasilan_bruto', 'biaya_jabatan', 'penghasilan_neto', 'pph_dipotong', 'tahun'},
        'compute': _compute_pekerjaan,
    },
    'utang': {
        'columns': ['kode', 'deskripsi', 'nama_kreditor', 'identitas_kreditor', 'negara_kreditor',
                    'tahun_peminjaman', 'jumlah', 'informasi_tambahan', 'tahun'],
        'int_columns': {'tahun_peminjaman', 'jumlah', 'tahun'},
    },
    'tanggungan': {
        'columns': ['nama', 'nik', 'tanggal_lahir', 'hubungan', 'pekerjaan', 'informasi_tambahan', 'tahun'],
        'int_columns': {'tahun'},
    },
    'harta_kas': {
        'columns': ['kode', 'deskripsi', 'nama_bank', 'no_rekening', 'lokasi', 'pemilik', 'saldo',
                    'informasi_tambahan', 'tahun'],
        'int_columns': {'saldo', 'tahun'},
    },
    'harta_piutang': {
        'columns': ['kode', 'deskripsi', 'nama_penerima', 'lokasi_penerima', 'identitas_penerima',
                    'tahun_mulai', 'nilai_piutang', 'saldo_piutang', 'informasi_tambahan', 'tahun'],
        'int_columns': {'tahun_mulai', 'nilai_piutang', 'saldo_piutang', 'tahun'},
    },
    'harta_investasi': {
        'columns': ['kode', 'deskripsi', 'negara', 'nama_institusi', 'npwp_institusi', 'no_akun',
                    'tahun_perolehan', 'harga_perolehan', 'nilai_saat_ini', 'informasi_tambahan', 'tahun'],
        'int_columns': {'tahun_perolehan', 'harga_perolehan', 'nilai_saat_ini', 'tahun'},
    },
    'harta_bergerak': {
        'columns': ['kode', 'deskripsi', 'merk', 'no_polisi', 'kepemilikan',
                    'tahun_perolehan', 'harga_perolehan', 'nilai_saat_ini', 'informasi_tambahan', 'tahun'],
        'int_columns': {'tahun_perolehan', 'harga_perolehan', 'nilai_saat_ini', 'tahun'},
    },
    'harta_tidak_bergerak': {
        'columns': ['kode', 'deskripsi', 'lokasi', 'luas_tanah', 'luas_bangunan',
                    'tahun_perolehan', 'harga_perolehan', 'nilai_saat_ini', 'sertifikat',
                    'informasi_tambahan', 'tahun'],
        'int_columns': {'luas_tanah', 'luas_bangunan', 'tahun_perolehan', 'harga_perolehan',
                         'nilai_saat_ini', 'tahun'},
    },
    'harta_lainnya': {
        'columns': ['kode', 'deskripsi', 'tahun_perolehan', 'bukti_kepemilikan', 'harga_perolehan',
                    'nilai_saat_ini', 'keterangan', 'tahun'],
        'int_columns': {'tahun_perolehan', 'harga_perolehan', 'nilai_saat_ini', 'tahun'},
    },
    'penghasilan_final': {
        'columns': ['kode', 'deskripsi', 'jumlah_bruto', 'pph_final', 'informasi_tambahan', 'tahun'],
        'int_columns': {'jumlah_bruto', 'pph_final', 'tahun'},
    },
    'penghasilan_bukan_objek': {
        'columns': ['kode', 'deskripsi', 'jumlah', 'informasi_tambahan', 'tahun'],
        'int_columns': {'jumlah', 'tahun'},
    },
    'zakat': {
        'columns': ['deskripsi', 'lembaga', 'jumlah', 'tahun'],
        'int_columns': {'jumlah', 'tahun'},
    },
    'catatan_penghasilan': {
        'columns': ['tanggal', 'deskripsi', 'perkiraan_jumlah', 'kategori', 'status', 'keterangan', 'tahun'],
        'int_columns': {'perkiraan_jumlah', 'tahun'},
        'compute': _compute_catatan,
    },
}

# Tabel "posisi" (saldo harta/utang/tanggungan) yang wajar disalin sebagai titik awal
# tahun berikutnya. Penghasilan/final/bukan-objek/zakat/catatan tidak disalin karena
# itu transaksi yang memang berbeda tiap tahun.
CARRY_FORWARD_TABLES = [
    'harta_kas', 'harta_piutang', 'harta_investasi', 'harta_bergerak',
    'harta_tidak_bergerak', 'harta_lainnya', 'utang', 'tanggungan',
]

def save_row(tabel, data, row_id=None):
    spec = TABLE_SPEC[tabel]
    values = {}
    for col in spec['columns']:
        v = data.get(col, '')
        if col in spec['int_columns']:
            v = int(v or 0)
        values[col] = v
    if spec.get('compute'):
        values = spec['compute'](values)
    cols = spec['columns']
    vals = [values[c] for c in cols]
    with get_db() as conn:
        if row_id is None:
            placeholders = ','.join('?' for _ in cols)
            conn.execute(f'INSERT INTO {tabel} ({",".join(cols)}) VALUES ({placeholders})', vals)
        else:
            set_clause = ','.join(f'{c}=?' for c in cols)
            conn.execute(f'UPDATE {tabel} SET {set_clause} WHERE id=?', vals + [row_id])
        conn.commit()

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/api/identitas', methods=['GET', 'POST'])
def identitas():
    if request.method == 'POST':
        data = request.json
        with get_db() as conn:
            conn.execute('''UPDATE wp_identitas SET
                nik=?, npwp=?, nama=?, telepon=?, email=?, status_kawin=?, ptkp_status=?
                WHERE id=1''',
                (data['nik'], data['npwp'], data['nama'], data['telepon'],
                 data['email'], data['status_kawin'], data['ptkp_status']))
            conn.commit()
        return jsonify({'status': 'ok'})
    else:
        with get_db() as conn:
            row = conn.execute('SELECT * FROM wp_identitas WHERE id=1').fetchone()
            return jsonify(dict(row) if row else {})

@app.route('/api/item/<tabel>', methods=['POST'])
def api_tambah(tabel):
    if tabel not in TABLE_SPEC:
        return jsonify({'status': 'error', 'msg': 'Tabel tidak dikenal'}), 400
    try:
        save_row(tabel, request.json or {})
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 400
    return jsonify({'status': 'ok'})

@app.route('/api/item/<tabel>/<int:id>', methods=['PUT'])
def api_edit(tabel, id):
    if tabel not in TABLE_SPEC:
        return jsonify({'status': 'error', 'msg': 'Tabel tidak dikenal'}), 400
    try:
        save_row(tabel, request.json or {}, row_id=id)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 400
    return jsonify({'status': 'ok'})

@app.route('/api/item/<tabel>/<int:id>', methods=['DELETE'])
def api_hapus(tabel, id):
    if tabel not in TABLE_SPEC:
        return jsonify({'status': 'error', 'msg': 'Tabel tidak dikenal'}), 400
    with get_db() as conn:
        conn.execute(f'DELETE FROM {tabel} WHERE id=?', (id,))
        conn.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/salin_tahun', methods=['POST'])
def api_salin_tahun():
    data = request.json or {}
    try:
        dari = int(data.get('dari_tahun', 0))
        ke = int(data.get('ke_tahun', 0))
    except (TypeError, ValueError):
        return jsonify({'status': 'error', 'msg': 'Tahun tidak valid'}), 400
    if not dari or not ke or dari == ke:
        return jsonify({'status': 'error', 'msg': 'Tahun tidak valid'}), 400
    hasil = {}
    with get_db() as conn:
        for tabel in CARRY_FORWARD_TABLES:
            spec = TABLE_SPEC[tabel]
            cols = [c for c in spec['columns'] if c != 'tahun']
            rows = conn.execute(f'SELECT {",".join(cols)} FROM {tabel} WHERE tahun=?', (dari,)).fetchall()
            for r in rows:
                vals = [r[c] for c in cols] + [ke]
                placeholders = ','.join('?' for _ in cols) + ',?'
                conn.execute(f'INSERT INTO {tabel} ({",".join(cols)},tahun) VALUES ({placeholders})', vals)
            hasil[tabel] = len(rows)
        conn.commit()
    return jsonify({'status': 'ok', 'hasil': hasil})

def compute_tahun_data(conn, tahun):
    identitas = conn.execute('SELECT * FROM wp_identitas WHERE id=1').fetchone()
    identitas = dict(identitas) if identitas else {}
    ptkp_status = identitas.get('ptkp_status') or 'TK/0'
    ptkp = get_ptkp(ptkp_status)

    def get_all(table):
        rows = conn.execute(f'SELECT * FROM {table} WHERE tahun=? ORDER BY id', (tahun,)).fetchall()
        return [dict(r) for r in rows]

    pekerjaan = get_all('penghasilan_pekerjaan')
    utang = get_all('utang')
    tanggungan = get_all('tanggungan')
    kas = get_all('harta_kas')
    piutang = get_all('harta_piutang')
    investasi = get_all('harta_investasi')
    bergerak = get_all('harta_bergerak')
    tidakbergerak = get_all('harta_tidak_bergerak')
    lainnya = get_all('harta_lainnya')
    final = get_all('penghasilan_final')
    bukanobjek = get_all('penghasilan_bukan_objek')
    zakat = get_all('zakat')
    catatan = get_all('catatan_penghasilan')

    total_bruto = sum(r['penghasilan_bruto'] for r in pekerjaan)
    total_neto = sum(r['penghasilan_neto'] for r in pekerjaan)
    total_pph_dipotong = sum(r['pph_dipotong'] for r in pekerjaan)
    total_utang = sum(r['jumlah'] for r in utang)
    total_zakat = sum(r['jumlah'] for r in zakat)
    total_final_bruto = sum(r['jumlah_bruto'] for r in final)
    total_final_pph = sum(r['pph_final'] for r in final)
    total_bukan_objek = sum(r['jumlah'] for r in bukanobjek)

    total_hp = 0
    total_nilai = 0
    for item in kas:
        total_hp += item['saldo']
        total_nilai += item['saldo']
    for item in piutang:
        total_hp += item['nilai_piutang']
        total_nilai += item['saldo_piutang']
    for item in investasi:
        total_hp += item['harga_perolehan']
        total_nilai += item['nilai_saat_ini']
    for item in bergerak:
        total_hp += item['harga_perolehan']
        total_nilai += item['nilai_saat_ini']
    for item in tidakbergerak:
        total_hp += item['harga_perolehan']
        total_nilai += item['nilai_saat_ini']
    for item in lainnya:
        total_hp += item['harga_perolehan']
        total_nilai += item['nilai_saat_ini']

    neto_setelah_zakat = max(0, total_neto - total_zakat)
    pkp = max(0, neto_setelah_zakat - ptkp)
    pph_terutang = hitung_pph(neto_setelah_zakat, ptkp)
    status_bayar = pph_terutang - total_pph_dipotong
    kekayaan = total_nilai - total_utang

    return {
        'identitas': identitas,
        'pekerjaan': pekerjaan, 'utang': utang, 'tanggungan': tanggungan,
        'kas': kas, 'piutang': piutang, 'investasi': investasi,
        'bergerak': bergerak, 'tidakbergerak': tidakbergerak, 'lainnya': lainnya,
        'final': final, 'bukanobjek': bukanobjek, 'zakat': zakat, 'catatan': catatan,
        'rekap': {
            'total_bruto': total_bruto,
            'total_neto': total_neto,
            'total_zakat': total_zakat,
            'neto_setelah_zakat': neto_setelah_zakat,
            'pkp': pkp,
            'pph_terutang': pph_terutang,
            'status_bayar': status_bayar,
            'total_pph_dipotong': total_pph_dipotong,
            'total_final_bruto': total_final_bruto,
            'total_final_pph': total_final_pph,
            'total_bukan_objek': total_bukan_objek,
            'total_utang': total_utang,
            'total_hp': total_hp,
            'total_nilai': total_nilai,
            'kekayaan': kekayaan,
            'ptkp': ptkp,
            'ptkp_status': ptkp_status,
        }
    }

def get_tahun_list(conn):
    now_year = datetime.now().year
    tahun_set = set(range(now_year - 10, now_year + 1))
    for t in TABLE_SPEC:
        for r in conn.execute(f'SELECT DISTINCT tahun FROM {t}').fetchall():
            if r['tahun'] is not None:
                tahun_set.add(r['tahun'])
    return sorted(tahun_set, reverse=True)

@app.route('/api/data')
def api_data():
    tahun = request.args.get('tahun', str(datetime.now().year))
    with get_db() as conn:
        d = compute_tahun_data(conn, tahun)
        d['rekap']['tahun_filter'] = int(tahun)
        d['rekap']['list_tahun'] = get_tahun_list(conn)
    d.pop('identitas')
    return jsonify(d)

def format_rp(n):
    return 'Rp ' + '{:,}'.format(int(n or 0)).replace(',', '.')

def _pdf_col_widths(n, total=500, first_weight=1.6):
    if n == 1:
        return [total]
    first = total * first_weight / (first_weight + (n - 1))
    rest = (total - first) / (n - 1)
    return [first] + [rest] * (n - 1)

@app.route('/api/export_pdf')
def export_pdf():
    tahun = request.args.get('tahun', str(datetime.now().year))
    with get_db() as conn:
        d = compute_tahun_data(conn, tahun)
    idnt = d['identitas']
    r = d['rekap']

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=16 * mm, bottomMargin=14 * mm,
                             leftMargin=15 * mm, rightMargin=15 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleX', parent=styles['Title'], fontSize=16, spaceAfter=2)
    sub_style = ParagraphStyle('SubX', parent=styles['Normal'], fontSize=9, textColor=colors.grey, spaceAfter=6)
    note_style = ParagraphStyle('NoteX', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#b02a37'), spaceAfter=10)
    h2_style = ParagraphStyle('H2X', parent=styles['Heading2'], fontSize=12, spaceBefore=14, spaceAfter=6,
                               textColor=colors.HexColor('#0d6efd'))
    cell_style = ParagraphStyle('CellX', parent=styles['Normal'], fontSize=7.5, leading=9.5)
    header_cell_style = ParagraphStyle('HeaderCellX', parent=cell_style, fontName='Helvetica-Bold')

    elems = []
    elems.append(Paragraph('Ringkasan Data Pajak Pribadi', title_style))
    elems.append(Paragraph(
        f"{idnt.get('nama') or '-'} &middot; NIK {idnt.get('nik') or '-'} &middot; Tahun Pajak {tahun} "
        f"&middot; Dicetak {tanggal_indonesia(datetime.now())}", sub_style))
    elems.append(Paragraph(
        'Dokumen ini adalah ringkasan pribadi untuk mempermudah transkrip data ke formulir SPT di Coretax DJP. '
        'BUKAN dokumen SPT resmi, dan tidak perlu/tidak bisa diunggah ke Coretax.', note_style))

    def table_section(title, headers, rows, first_weight=1.6):
        elems.append(Paragraph(title, h2_style))
        if not rows:
            elems.append(Paragraph('Tidak ada data.', styles['Normal']))
            return
        col_widths = _pdf_col_widths(len(headers), first_weight=first_weight)
        header_row = [Paragraph(h, header_cell_style) for h in headers]
        body_rows = [[Paragraph(str(v) if v not in (None, '') else '-', cell_style) for v in row] for row in rows]
        t = Table([header_row] + body_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f9')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d8dee6')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 6))

    status_label = 'Nihil'
    if r['status_bayar'] > 0:
        status_label = 'Kurang Bayar ' + format_rp(r['status_bayar'])
    elif r['status_bayar'] < 0:
        status_label = 'Lebih Bayar ' + format_rp(abs(r['status_bayar']))

    table_section('Identitas Wajib Pajak', ['Field', 'Nilai'], [
        ['NIK', idnt.get('nik')],
        ['NPWP', idnt.get('npwp')],
        ['Nama', idnt.get('nama')],
        ['Status Kawin', idnt.get('status_kawin')],
        ['Status PTKP', idnt.get('ptkp_status')],
    ], first_weight=0.6)

    table_section('Ringkasan Perhitungan Pajak', ['Komponen', 'Jumlah'], [
        ['Total Penghasilan Bruto (Pekerjaan)', format_rp(r['total_bruto'])],
        ['Total Penghasilan Neto (Pekerjaan)', format_rp(r['total_neto'])],
        ['Zakat/Pengurang', format_rp(r['total_zakat'])],
        ['Penghasilan Neto Setelah Zakat', format_rp(r['neto_setelah_zakat'])],
        [f"PTKP ({r['ptkp_status']})", format_rp(r['ptkp'])],
        ['Penghasilan Kena Pajak (PKP)', format_rp(r['pkp'])],
        ['PPh Terutang', format_rp(r['pph_terutang'])],
        ['Total PPh Dipotong (Kredit Pajak)', format_rp(r['total_pph_dipotong'])],
        ['Status Akhir', status_label],
    ], first_weight=1.2)

    table_section('Penghasilan dari Pekerjaan (Bukti Potong 1721-A1)',
        ['Pemberi Kerja', 'NPWP', 'Bruto', 'Biaya Jabatan', 'Neto', 'PPh Dipotong', 'Info Tambahan'],
        [[p['nama_pemberi'], p['npwp_pemberi'], format_rp(p['penghasilan_bruto']),
          format_rp(p['biaya_jabatan']), format_rp(p['penghasilan_neto']), format_rp(p['pph_dipotong']),
          p['informasi_tambahan']]
         for p in d['pekerjaan']])

    table_section('Penghasilan Dikenakan Pajak Final', ['Kode', 'Deskripsi', 'Bruto', 'PPh Final', 'Info Tambahan'],
        [[f['kode'], f['deskripsi'], format_rp(f['jumlah_bruto']), format_rp(f['pph_final']),
          f['informasi_tambahan']] for f in d['final']])

    table_section('Penghasilan Bukan Objek Pajak', ['Kode', 'Deskripsi', 'Jumlah', 'Info Tambahan'],
        [[b['kode'], b['deskripsi'], format_rp(b['jumlah']), b['informasi_tambahan']] for b in d['bukanobjek']])

    table_section('Zakat / Sumbangan Keagamaan Wajib', ['Deskripsi', 'Lembaga', 'Jumlah'],
        [[z['deskripsi'], z['lembaga'], format_rp(z['jumlah'])] for z in d['zakat']])

    elems.append(PageBreak())

    table_section('Daftar Utang', ['Kode', 'Deskripsi', 'Kreditor', 'Identitas', 'Negara', 'Th Pinjam', 'Jumlah', 'Info Tambahan'],
        [[u['kode'], u['deskripsi'], u['nama_kreditor'], u['identitas_kreditor'], u['negara_kreditor'],
          u['tahun_peminjaman'], format_rp(u['jumlah']), u['informasi_tambahan']] for u in d['utang']])

    table_section('Daftar Susunan Anggota Keluarga (Tanggungan)',
        ['Nama', 'NIK', 'Tgl Lahir', 'Hubungan', 'Pekerjaan', 'Info Tambahan'],
        [[t['nama'], t['nik'], t['tanggal_lahir'], t['hubungan'], t['pekerjaan'], t['informasi_tambahan']]
         for t in d['tanggungan']])

    elems.append(PageBreak())
    elems.append(Paragraph('Daftar Harta pada Akhir Tahun Pajak', h2_style))

    table_section('Kas dan Setara Kas',
        ['Kode', 'Deskripsi', 'Bank', 'Rekening', 'Lokasi', 'Pemilik', 'Saldo', 'Info Tambahan'],
        [[k['kode'], k['deskripsi'], k['nama_bank'], k['no_rekening'], k['lokasi'], k['pemilik'],
          format_rp(k['saldo']), k['informasi_tambahan']] for k in d['kas']])

    table_section('Piutang', ['Kode', 'Deskripsi', 'Penerima', 'Lokasi', 'Mulai', 'Nilai', 'Saldo', 'Info Tambahan'],
        [[p['kode'], p['deskripsi'], p['nama_penerima'], p['lokasi_penerima'], p['tahun_mulai'],
          format_rp(p['nilai_piutang']), format_rp(p['saldo_piutang']), p['informasi_tambahan']] for p in d['piutang']])

    table_section('Investasi/Sekuritas', ['Kode', 'Deskripsi', 'Institusi', 'Th Perolehan', 'Harga Perolehan', 'Nilai Saat Ini', 'Info Tambahan'],
        [[i['kode'], i['deskripsi'], i['nama_institusi'], i['tahun_perolehan'],
          format_rp(i['harga_perolehan']), format_rp(i['nilai_saat_ini']), i['informasi_tambahan']] for i in d['investasi']])

    table_section('Harta Bergerak', ['Kode', 'Deskripsi', 'Merk', 'Th Perolehan', 'Harga Perolehan', 'Nilai Saat Ini', 'Info Tambahan'],
        [[b['kode'], b['deskripsi'], b['merk'], b['tahun_perolehan'],
          format_rp(b['harga_perolehan']), format_rp(b['nilai_saat_ini']), b['informasi_tambahan']] for b in d['bergerak']])

    table_section('Harta Tidak Bergerak', ['Kode', 'Deskripsi', 'Lokasi', 'Th Perolehan', 'Harga Perolehan', 'Nilai Saat Ini', 'Info Tambahan'],
        [[t['kode'], t['deskripsi'], t['lokasi'], t['tahun_perolehan'],
          format_rp(t['harga_perolehan']), format_rp(t['nilai_saat_ini']), t['informasi_tambahan']] for t in d['tidakbergerak']])

    table_section('Harta Lainnya', ['Kode', 'Deskripsi', 'Th Perolehan', 'Bukti Kepemilikan', 'Harga Perolehan', 'Nilai Saat Ini', 'Info Tambahan'],
        [[l['kode'], l['deskripsi'], l['tahun_perolehan'], l['bukti_kepemilikan'],
          format_rp(l['harga_perolehan']), format_rp(l['nilai_saat_ini']), l['keterangan']] for l in d['lainnya']])

    doc.build(elems)
    buf.seek(0)
    nama_file = f"ringkasan-pajak-{tahun}.pdf"
    return Response(buf.read(), mimetype='application/pdf',
                     headers={'Content-Disposition': f'attachment; filename="{nama_file}"'})

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PajakSaya - Coretax Lengkap</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        body { background: #f4f6f9; padding-bottom: 40px; }
        .topbar { background: white; border-bottom: 1px solid #e9ecef; padding: 14px 24px;
                  position: sticky; top: 0; z-index: 1030; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }
        .topbar h4 { margin: 0; font-weight: 700; }
        .topbar small { color: #8a93a3; }
        .container-fluid { max-width: 1300px; }
        .card { border-radius: 14px; border: none; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; }
        .card-header { background: white; border-bottom: 1px solid #eef0f3; font-weight: 600; border-radius: 14px 14px 0 0 !important; }
        .card-header .bi { margin-right: 6px; color: #0d6efd; }
        .stat-card h6 { color: #8a93a3; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .03em; margin-bottom: 6px; }
        .stat-card h4 { font-weight: 700; margin: 0; }
        .section-label { color: #8a93a3; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .05em;
                          margin: 22px 0 8px 4px; font-weight: 700; }
        .table th { background: #f8f9fa; font-size: 0.82rem; color: #667; white-space: nowrap; }
        .table td { font-size: 0.88rem; vertical-align: middle; }
        .table-hover tbody tr:hover { background: #f6f9ff; }
        .form-label-sm { font-size: 0.78rem; color: #6c757d; margin-bottom: 2px; display: block; }
        .btn-cancel-edit { display: none; }
        .btn-cancel-edit.show { display: inline-block; }
        .badge-status { font-size: 1.1rem; padding: 10px 18px; }
        .subform-title { font-weight: 700; font-size: 0.95rem; margin-bottom: 8px; }
        .field-hint-icon { color: #adb5bd; font-size: 0.8rem; margin-left: 4px; cursor: help; }
        .field-hint-icon:hover { color: #0d6efd; }
        .tooltip-inner { max-width: 280px; text-align: left; }

        .app-shell { display: flex; align-items: flex-start; gap: 20px; max-width: 1320px; margin: 20px auto 40px; padding: 0 20px; }
        .sidebar { width: 235px; flex: 0 0 235px; background: white; border-radius: 14px;
                   box-shadow: 0 2px 10px rgba(0,0,0,0.05); padding: 10px; position: sticky; top: 90px; border: none; }
        .side-group-label { font-size: 0.68rem; text-transform: uppercase; letter-spacing: .06em; color: #adb5bd;
                             font-weight: 700; padding: 14px 10px 4px; }
        .sidebar .list-group-item.side-link { display: flex; align-items: center; gap: 10px; padding: 9px 10px;
                             border-radius: 10px; color: #495057; text-decoration: none; font-size: 0.88rem;
                             font-weight: 500; border: none; margin-bottom: 2px; }
        .side-link i { font-size: 1rem; width: 18px; text-align: center; color: #8a93a3; }
        .sidebar .list-group-item.side-link:hover { background: #f1f4f9; color: #0d6efd; }
        .sidebar .list-group-item.side-link.active { background: #0d6efd; color: white; }
        .side-link.active i { color: white; }
        .content { flex: 1 1 auto; min-width: 0; }
        @media (max-width: 900px) {
            .app-shell { flex-direction: column; padding: 0 12px; }
            .sidebar { width: 100%; flex: none; position: static; display: flex; flex-wrap: nowrap;
                       overflow-x: auto; gap: 4px; }
            .side-group-label { display: none; }
            .side-link { flex: 0 0 auto; white-space: nowrap; }
        }
    </style>
</head>
<body>
<div class="topbar d-flex justify-content-between align-items-center flex-wrap gap-2">
    <div>
        <h4>📊 PajakSaya <small class="fw-normal" style="font-size:0.6rem;">versi Coretax PER-11/PJ/2025</small></h4>
        <small>Aplikasi pribadi pencatatan SPT Tahunan Orang Pribadi</small>
    </div>
    <div class="d-flex align-items-center gap-2">
        <button class="btn btn-outline-success btn-sm" onclick="exportPdf()"><i class="bi bi-file-earmark-pdf"></i> Export Ringkasan (PDF)</button>
        <button class="btn btn-outline-primary btn-sm" onclick="salinDariTahunLalu()"><i class="bi bi-copy"></i> Salin dari Tahun Lalu</button>
        <label for="tahunPajak" class="mb-0 fw-semibold">Tahun Pajak</label>
        <select id="tahunPajak" class="form-select" style="width:auto;" onchange="ambilData()"></select>
    </div>
</div>

<div class="app-shell">
    <nav class="sidebar list-group" id="myTab" role="tablist">
        <div class="side-group-label">Ringkasan</div>
        <a class="list-group-item list-group-item-action side-link active" id="tab-btn-dashboard" data-bs-toggle="list" href="#dashboard" role="tab"><i class="bi bi-speedometer2"></i>Dashboard</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-review" data-bs-toggle="list" href="#review" role="tab"><i class="bi bi-clipboard-check"></i>Review & Estimasi</a>
        <div class="side-group-label">Bantuan</div>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-tanya" data-bs-toggle="list" href="#tanya" role="tab"><i class="bi bi-search-heart"></i>Tanya / Klasifikasi</a>
        <div class="side-group-label">Pencatatan</div>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-catatan" data-bs-toggle="list" href="#catatan" role="tab"><i class="bi bi-journal-text"></i>Catatan Penghasilan</a>
        <div class="side-group-label">Penghasilan</div>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-pekerjaan" data-bs-toggle="list" href="#pekerjaan" role="tab"><i class="bi bi-briefcase"></i>Pekerjaan</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-penghasilanlain" data-bs-toggle="list" href="#penghasilanlain" role="tab"><i class="bi bi-cash-coin"></i>Penghasilan Lain</a>
        <div class="side-group-label">Keluarga & Utang</div>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-tanggungan" data-bs-toggle="list" href="#tanggungan" role="tab"><i class="bi bi-people"></i>Tanggungan</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-utang" data-bs-toggle="list" href="#utang" role="tab"><i class="bi bi-credit-card"></i>Utang</a>
        <div class="side-group-label">Harta</div>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-kas" data-bs-toggle="list" href="#kas" role="tab"><i class="bi bi-wallet2"></i>Kas</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-piutang" data-bs-toggle="list" href="#piutang" role="tab"><i class="bi bi-receipt"></i>Piutang</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-investasi" data-bs-toggle="list" href="#investasi" role="tab"><i class="bi bi-graph-up-arrow"></i>Investasi</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-bergerak" data-bs-toggle="list" href="#bergerak" role="tab"><i class="bi bi-car-front"></i>Bergerak</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-tidakbergerak" data-bs-toggle="list" href="#tidakbergerak" role="tab"><i class="bi bi-house"></i>Tidak Bergerak</a>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-lainnya" data-bs-toggle="list" href="#lainnya" role="tab"><i class="bi bi-box-seam"></i>Lainnya</a>
        <div class="side-group-label">Profil</div>
        <a class="list-group-item list-group-item-action side-link" id="tab-btn-identitas" data-bs-toggle="list" href="#identitas" role="tab"><i class="bi bi-person-vcard"></i>Identitas</a>
    </nav>
    <main class="content">
    <div class="tab-content">

        <div class="tab-pane active" id="dashboard">
            <div class="section-label">Penghasilan & PPh Terutang</div>
            <div class="row g-3">
                <div class="col-md-3"><div class="card stat-card"><div class="card-body text-center"><h6>Total Bruto Pekerjaan</h6><h4 id="totalGross">Rp 0</h4></div></div></div>
                <div class="col-md-3"><div class="card stat-card"><div class="card-body text-center"><h6>Zakat/Pengurang</h6><h4 id="totalZakat">Rp 0</h4></div></div></div>
                <div class="col-md-3"><div class="card stat-card"><div class="card-body text-center"><h6>Neto Setelah Zakat</h6><h4 id="totalNeto">Rp 0</h4></div></div></div>
                <div class="col-md-3"><div class="card stat-card"><div class="card-body text-center"><h6>PTKP</h6><h4 id="ptkpDisplay">Rp 0</h4></div></div></div>
            </div>
            <div class="row g-3 mt-1">
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>PPh Terutang (Ps 17)</h6><h4 id="pphTerutang">Rp 0</h4></div></div></div>
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Total PPh Dipotong (Kredit)</h6><h4 id="totalPphDipotong">Rp 0</h4></div></div></div>
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center d-flex flex-column justify-content-center h-100">
                    <span id="statusBadge" class="badge bg-secondary badge-status">Nihil</span>
                </div></div></div>
            </div>

            <div class="section-label">Penghasilan Final & Bukan Objek Pajak <span class="text-muted fw-normal text-lowercase">(informasi, tidak memengaruhi PPh Ps 17)</span></div>
            <div class="row g-3">
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Total Penghasilan Final (Bruto)</h6><h4 id="totalFinalBruto">Rp 0</h4></div></div></div>
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Total PPh Final Dibayar</h6><h4 id="totalFinalPph">Rp 0</h4></div></div></div>
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Total Bukan Objek Pajak</h6><h4 id="totalBukanObjek">Rp 0</h4></div></div></div>
            </div>

            <div class="section-label">Harta & Kekayaan</div>
            <div class="row g-3">
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Total Harta (Nilai)</h6><h4 id="totalHarta">Rp 0</h4></div></div></div>
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Total Utang</h6><h4 id="totalUtang">Rp 0</h4></div></div></div>
                <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Kekayaan Bersih</h6><h4 id="kekayaanBersih">Rp 0</h4></div></div></div>
            </div>

            <div class="card mt-3"><div class="card-header"><i class="bi bi-list-columns-reverse"></i>Ikhtisar Harta</div>
            <div class="card-body">
                <div class="table-responsive">
                <table class="table table-sm table-hover">
                    <thead><tr><th>Kategori</th><th class="text-end">Harga Perolehan</th><th class="text-end">Nilai Saat Ini</th></tr></thead>
                    <tbody id="ikhtisarBody"></tbody>
                </table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="review">
            <div class="card"><div class="card-header"><i class="bi bi-clipboard-check"></i>Checklist Kelengkapan</div>
            <div class="card-body">
                <ul class="list-group list-group-flush" id="checklistBody"></ul>
            </div></div>

            <div class="card"><div class="card-header"><i class="bi bi-arrow-left-right"></i>Rekonsiliasi Kekayaan</div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Kekayaan Tahun Lalu</h6><h4 id="kekayaanLalu">Rp 0</h4></div></div></div>
                    <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Kekayaan Tahun Ini</h6><h4 id="kekayaanIni">Rp 0</h4></div></div></div>
                    <div class="col-md-4"><div class="card stat-card"><div class="card-body text-center"><h6>Selisih</h6><h4 id="selisihKekayaan">Rp 0</h4></div></div></div>
                </div>
                <small class="text-muted d-block mt-2">Sebagai gambaran kasar, kenaikan kekayaan idealnya sejalan dengan penghasilan neto setelah pajak dikurangi konsumsi/pengeluaran tahun berjalan. Ini bukan validasi resmi, hanya pengingat untuk dicek sendiri.</small>
            </div></div>

            <div class="card"><div class="card-header"><i class="bi bi-calculator"></i>Estimasi Pajak Tahun Ini</div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-6"><div class="card stat-card"><div class="card-body text-center"><h6>PPh Terutang</h6><h4 id="reviewPphTerutang">Rp 0</h4></div></div></div>
                    <div class="col-md-6"><div class="card stat-card"><div class="card-body text-center d-flex flex-column justify-content-center h-100"><span id="reviewStatusBadge" class="badge bg-secondary badge-status">Nihil</span></div></div></div>
                </div>
            </div></div>

            <div class="card"><div class="card-header"><i class="bi bi-exclamation-triangle text-warning"></i>Catatan Penghasilan Belum Diproses</div>
            <div class="card-body">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Tanggal</th><th>Deskripsi</th><th class="text-end">Perkiraan</th><th>Kategori</th></tr></thead><tbody id="tabelCatatanBelumReview"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="tanya">
            <div class="card"><div class="card-header"><i class="bi bi-search-heart"></i>Tanya: Ini Masuk Kategori Apa?</div>
            <div class="card-body">
                <div class="row g-2">
                    <div class="col-md-10"><input id="tanya_input" class="form-control form-control-lg" placeholder="Ketik transaksi/penghasilan kamu, misal: deposit ke bibit, dapat hibah, jual saham, sewa kos..." oninput="cariSaran()"></div>
                    <div class="col-md-2"><button class="btn btn-primary btn-lg w-100" onclick="cariSaran()"><i class="bi bi-search"></i> Cari</button></div>
                </div>
                <small class="text-muted d-block mt-2">Ini panduan umum hasil rangkuman dari berbagai sumber resmi (DJP, Ortax, DDTC, dll — per Agustus 2026), <b>bukan nasihat pajak resmi</b>. Untuk transaksi besar, tidak biasa, atau kalau ragu, konsultasikan ke Account Representative (AR) pajak kamu atau konsultan pajak bersertifikat.</small>
            </div></div>
            <div id="tanyaHasil"></div>
        </div>

        <div class="tab-pane" id="catatan">
            <div class="card"><div class="card-header"><i class="bi bi-journal-plus"></i>Tambah Catatan Penghasilan</div>
            <div class="card-body" id="form_catatan_penghasilan">
                <input type="hidden" id="ctt_status" value="belum">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Tanggal</span><input id="ctt_tanggal" type="date" class="form-control"></div>
                    <div class="col-3"><span class="form-label-sm">Deskripsi</span><input id="ctt_deskripsi" class="form-control" placeholder="Cth: Honor desain logo"></div>
                    <div class="col-2"><span class="form-label-sm">Perkiraan Jumlah</span><input id="ctt_jumlah" class="form-control money" placeholder="Perkiraan Jumlah" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Kategori</span><select id="ctt_kategori" class="form-select">
                        <option value="Pekerjaan">Pekerjaan</option>
                        <option value="Final">Final</option>
                        <option value="Bukan Objek">Bukan Objek</option>
                        <option value="Lainnya">Lainnya</option>
                    </select></div>
                    <div class="col-2"><span class="form-label-sm">Keterangan</span><input id="ctt_keterangan" class="form-control" placeholder="Keterangan"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_catatan_penghasilan" onclick="submitForm(FORM_CONFIG.catatan)">Simpan</button>
                    </div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_catatan_penghasilan" onclick="cancelEdit(FORM_CONFIG.catatan)">Batal Edit</button>
                <small class="text-muted d-block mt-2">Catatan cepat untuk penghasilan di luar gaji supaya tidak lupa. Belum masuk hitungan pajak - klasifikasikan nanti ke tab Pekerjaan/Penghasilan Lain, lalu tandai "Sudah".</small>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:380px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Tanggal</th><th>Deskripsi</th><th class="text-end">Perkiraan</th><th>Kategori</th><th>Status</th><th>Keterangan</th><th>Aksi</th></tr></thead><tbody id="tabelCatatan"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="pekerjaan">
            <div class="card"><div class="card-header"><i class="bi bi-briefcase"></i>Tambah Penghasilan Pekerjaan (Bukti Potong 1721-A1)</div>
            <div class="card-body" id="form_penghasilan_pekerjaan">
                <div class="row g-2">
                    <div class="col-3"><span class="form-label-sm">Nama Pemberi Kerja</span><input id="pkr_nama" class="form-control" placeholder="Nama Pemberi Kerja"></div>
                    <div class="col-2"><span class="form-label-sm">NPWP Pemberi Kerja</span><input id="pkr_npwp" class="form-control" placeholder="NPWP Pemberi Kerja"></div>
                    <div class="col-2"><span class="form-label-sm">Penghasilan Bruto</span><input id="pkr_bruto" class="form-control money" placeholder="Penghasilan Bruto" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">PPh Dipotong</span><input id="pkr_pph" class="form-control money" placeholder="PPh Dipotong" oninput="formatMoneyLive(this)"></div>
                    <div class="col-3 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_penghasilan_pekerjaan" onclick="submitForm(FORM_CONFIG.pekerjaan)">Simpan</button>
                        <button class="btn btn-outline-secondary btn-cancel-edit" id="cancel_penghasilan_pekerjaan" onclick="cancelEdit(FORM_CONFIG.pekerjaan)">Batal</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="pkr_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <small class="text-muted">* Biaya jabatan 5% (maks Rp 6.000.000/tahun) dihitung otomatis.</small>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:340px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Pemberi Kerja</th><th>NPWP</th><th class="text-end">Bruto</th><th class="text-end">Biaya</th><th class="text-end">Neto</th><th class="text-end">PPh Dipotong</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelPekerjaan"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="penghasilanlain">
            <div class="card"><div class="card-header"><i class="bi bi-cash-stack"></i>Penghasilan Dikenakan Pajak Final</div>
            <div class="card-body" id="form_penghasilan_final">
                <div class="row g-2">
                    <div class="col-3"><span class="form-label-sm">Jenis Penghasilan Final</span><select id="final_kode" class="form-select"></select></div>
                    <div class="col-3"><span class="form-label-sm">Jumlah Bruto</span><input id="final_bruto" class="form-control money" placeholder="Jumlah Bruto" oninput="formatMoneyLive(this)"></div>
                    <div class="col-3"><span class="form-label-sm">PPh Final Dibayar</span><input id="final_pph" class="form-control money" placeholder="PPh Final Dibayar" oninput="formatMoneyLive(this)"></div>
                    <div class="col-3 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_penghasilan_final" onclick="submitForm(FORM_CONFIG.final)">Simpan</button>
                        <button class="btn btn-outline-secondary btn-cancel-edit" id="cancel_penghasilan_final" onclick="cancelEdit(FORM_CONFIG.final)">Batal</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="final_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:220px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th class="text-end">Bruto</th><th class="text-end">PPh Final</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelFinal"></tbody></table>
                </div>
            </div></div>

            <div class="card"><div class="card-header"><i class="bi bi-gift"></i>Penghasilan Bukan Objek Pajak</div>
            <div class="card-body" id="form_penghasilan_bukan_objek">
                <div class="row g-2">
                    <div class="col-4"><span class="form-label-sm">Jenis Penghasilan</span><select id="bukanobjek_kode" class="form-select"></select></div>
                    <div class="col-4"><span class="form-label-sm">Jumlah</span><input id="bukanobjek_jumlah" class="form-control money" placeholder="Jumlah" oninput="formatMoneyLive(this)"></div>
                    <div class="col-4 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_penghasilan_bukan_objek" onclick="submitForm(FORM_CONFIG.bukanobjek)">Simpan</button>
                        <button class="btn btn-outline-secondary btn-cancel-edit" id="cancel_penghasilan_bukan_objek" onclick="cancelEdit(FORM_CONFIG.bukanobjek)">Batal</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="bukanobjek_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:220px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th class="text-end">Jumlah</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelBukanObjek"></tbody></table>
                </div>
            </div></div>

            <div class="card"><div class="card-header"><i class="bi bi-moon-stars"></i>Zakat / Sumbangan Keagamaan Wajib <span class="text-muted fw-normal text-lowercase">(pengurang sebelum PTKP)</span></div>
            <div class="card-body" id="form_zakat">
                <div class="row g-2">
                    <div class="col-4"><span class="form-label-sm">Deskripsi</span><input id="zkt_deskripsi" class="form-control" placeholder="Cth: Zakat Penghasilan"></div>
                    <div class="col-4"><span class="form-label-sm">Lembaga Penerima</span><input id="zkt_lembaga" class="form-control" placeholder="Cth: BAZNAS"></div>
                    <div class="col-2"><span class="form-label-sm">Jumlah</span><input id="zkt_jumlah" class="form-control money" placeholder="Jumlah" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_zakat" onclick="submitForm(FORM_CONFIG.zakat)">Simpan</button>
                        <button class="btn btn-outline-secondary btn-cancel-edit" id="cancel_zakat" onclick="cancelEdit(FORM_CONFIG.zakat)">Batal</button>
                    </div>
                </div>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:220px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Deskripsi</th><th>Lembaga</th><th class="text-end">Jumlah</th><th>Aksi</th></tr></thead><tbody id="tabelZakat"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="utang">
            <div class="card"><div class="card-header"><i class="bi bi-credit-card"></i>Tambah Utang</div>
            <div class="card-body" id="form_utang">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Kode</span><select id="utang_kode" class="form-select"></select></div>
                    <div class="col-2"><span class="form-label-sm">Nama Kreditor</span><input id="utang_nama" class="form-control" placeholder="Nama Kreditor"></div>
                    <div class="col-2"><span class="form-label-sm">NIK/NPWP Kreditor</span><input id="utang_identitas" class="form-control" placeholder="NIK/NPWP Kreditor"></div>
                    <div class="col-2"><span class="form-label-sm">Negara Kreditor</span><input id="utang_negara" class="form-control" placeholder="Negara Kreditor"></div>
                    <div class="col-1"><span class="form-label-sm">Th. Pinjam</span><input id="utang_th_pinjam" type="number" class="form-control" placeholder="Tahun"></div>
                    <div class="col-2"><span class="form-label-sm">Jumlah Utang</span><input id="utang_jumlah" class="form-control money" placeholder="Jumlah Utang" oninput="formatMoneyLive(this)"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_utang" onclick="submitForm(FORM_CONFIG.utang)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="utang_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_utang" onclick="cancelEdit(FORM_CONFIG.utang)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:340px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Kreditor</th><th>Identitas</th><th>Negara</th><th>Th. Pinjam</th><th class="text-end">Jumlah</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelUtang"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="tanggungan">
            <div class="card"><div class="card-header"><i class="bi bi-people"></i>Tambah Anggota Keluarga Tanggungan</div>
            <div class="card-body" id="form_tanggungan">
                <div class="row g-2">
                    <div class="col-3"><span class="form-label-sm">Nama</span><input id="tgg_nama" class="form-control" placeholder="Nama"></div>
                    <div class="col-2"><span class="form-label-sm">NIK</span><input id="tgg_nik" class="form-control" placeholder="NIK"></div>
                    <div class="col-2"><span class="form-label-sm">Tanggal Lahir</span><input id="tgg_lahir" type="date" class="form-control"></div>
                    <div class="col-2"><span class="form-label-sm">Hubungan</span><input id="tgg_hubungan" class="form-control" placeholder="Hubungan"></div>
                    <div class="col-2"><span class="form-label-sm">Pekerjaan</span><input id="tgg_pekerjaan" class="form-control" placeholder="Pekerjaan"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_tanggungan" onclick="submitForm(FORM_CONFIG.tanggungan)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="tgg_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_tanggungan" onclick="cancelEdit(FORM_CONFIG.tanggungan)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:340px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Nama</th><th>NIK</th><th>Tgl Lahir</th><th>Hubungan</th><th>Pekerjaan</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelTanggungan"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="kas">
            <div class="card"><div class="card-header"><i class="bi bi-wallet2"></i>Kas & Setara Kas</div>
            <div class="card-body" id="form_harta_kas">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Kode</span><select id="kas_kode" class="form-select"></select></div>
                    <div class="col-2"><span class="form-label-sm">Nama Bank</span><input id="kas_bank" class="form-control" placeholder="Nama Bank"></div>
                    <div class="col-2"><span class="form-label-sm">No Rekening</span><input id="kas_rek" class="form-control" placeholder="No Rekening"></div>
                    <div class="col-2"><span class="form-label-sm">Lokasi</span><input id="kas_lokasi" class="form-control" placeholder="Lokasi"></div>
                    <div class="col-2"><span class="form-label-sm">Pemilik</span><input id="kas_pemilik" class="form-control" placeholder="Pemilik"></div>
                    <div class="col-1"><span class="form-label-sm">Saldo</span><input id="kas_saldo" class="form-control money" placeholder="Saldo" oninput="formatMoneyLive(this)"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_harta_kas" onclick="submitForm(FORM_CONFIG.kas)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="kas_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_harta_kas" onclick="cancelEdit(FORM_CONFIG.kas)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:280px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Bank</th><th>Rekening</th><th>Lokasi</th><th>Pemilik</th><th class="text-end">Saldo</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelKas"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="piutang">
            <div class="card"><div class="card-header"><i class="bi bi-receipt"></i>Piutang</div>
            <div class="card-body" id="form_harta_piutang">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Kode</span><select id="piutang_kode" class="form-select"></select></div>
                    <div class="col-2"><span class="form-label-sm">Nama Penerima</span><input id="piutang_penerima" class="form-control" placeholder="Nama Penerima"></div>
                    <div class="col-2"><span class="form-label-sm">Lokasi</span><input id="piutang_lokasi" class="form-control" placeholder="Lokasi"></div>
                    <div class="col-2"><span class="form-label-sm">Identitas</span><input id="piutang_identitas" class="form-control" placeholder="Identitas"></div>
                    <div class="col-1"><span class="form-label-sm">Th Mulai</span><input id="piutang_mulai" type="number" class="form-control" placeholder="Tahun Mulai"></div>
                    <div class="col-2"><span class="form-label-sm">Nilai Piutang</span><input id="piutang_nilai" class="form-control money" placeholder="Nilai Piutang" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Saldo Piutang</span><input id="piutang_saldo" class="form-control money" placeholder="Saldo Piutang" oninput="formatMoneyLive(this)"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_harta_piutang" onclick="submitForm(FORM_CONFIG.piutang)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="piutang_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_harta_piutang" onclick="cancelEdit(FORM_CONFIG.piutang)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:280px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Penerima</th><th>Lokasi</th><th>Identitas</th><th>Mulai</th><th class="text-end">Nilai</th><th class="text-end">Saldo</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelPiutang"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="investasi">
            <div class="card"><div class="card-header"><i class="bi bi-graph-up-arrow"></i>Investasi/Sekuritas</div>
            <div class="card-body" id="form_harta_investasi">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Kode</span><select id="inv_kode" class="form-select"></select></div>
                    <div class="col-2"><span class="form-label-sm">Negara</span><input id="inv_negara" class="form-control" placeholder="Negara"></div>
                    <div class="col-2"><span class="form-label-sm">Institusi</span><input id="inv_institusi" class="form-control" placeholder="Institusi"></div>
                    <div class="col-2"><span class="form-label-sm">NPWP Institusi</span><input id="inv_npwp" class="form-control" placeholder="NPWP Institusi"></div>
                    <div class="col-2"><span class="form-label-sm">No Akun</span><input id="inv_akun" class="form-control" placeholder="No Akun"></div>
                    <div class="col-1"><span class="form-label-sm">Th Perol</span><input id="inv_th_perol" type="number" class="form-control" placeholder="Th Perol"></div>
                    <div class="col-2"><span class="form-label-sm">Harga Perolehan</span><input id="inv_harga" class="form-control money" placeholder="Harga Perolehan" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Nilai Saat Ini</span><input id="inv_nilai" class="form-control money" placeholder="Nilai Saat Ini" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_harta_investasi" onclick="submitForm(FORM_CONFIG.investasi)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="inv_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_harta_investasi" onclick="cancelEdit(FORM_CONFIG.investasi)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:280px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Negara</th><th>Institusi</th><th>NPWP</th><th>Akun</th><th>Th Perol</th><th class="text-end">Harga</th><th class="text-end">Nilai</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelInvestasi"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="bergerak">
            <div class="card"><div class="card-header"><i class="bi bi-car-front"></i>Harta Bergerak</div>
            <div class="card-body" id="form_harta_bergerak">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Kode</span><select id="bg_kode" class="form-select"></select></div>
                    <div class="col-2"><span class="form-label-sm">Merk/Model</span><input id="bg_merk" class="form-control" placeholder="Merk/Model"></div>
                    <div class="col-2"><span class="form-label-sm">No Polisi</span><input id="bg_nopol" class="form-control" placeholder="No Polisi"></div>
                    <div class="col-2"><span class="form-label-sm">Kepemilikan</span><input id="bg_kepemilikan" class="form-control" placeholder="Kepemilikan"></div>
                    <div class="col-1"><span class="form-label-sm">Th Perol</span><input id="bg_th_perol" type="number" class="form-control" placeholder="Th Perol"></div>
                    <div class="col-2"><span class="form-label-sm">Harga Perolehan</span><input id="bg_harga" class="form-control money" placeholder="Harga Perolehan" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Nilai Saat Ini</span><input id="bg_nilai" class="form-control money" placeholder="Nilai Saat Ini" oninput="formatMoneyLive(this)"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_harta_bergerak" onclick="submitForm(FORM_CONFIG.bergerak)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="bg_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_harta_bergerak" onclick="cancelEdit(FORM_CONFIG.bergerak)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:280px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Merk</th><th>No Pol</th><th>Kepemilikan</th><th>Th Perol</th><th class="text-end">Harga</th><th class="text-end">Nilai</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelBergerak"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="tidakbergerak">
            <div class="card"><div class="card-header"><i class="bi bi-house"></i>Harta Tidak Bergerak</div>
            <div class="card-body" id="form_harta_tidak_bergerak">
                <div class="row g-2">
                    <div class="col-2"><span class="form-label-sm">Kode</span><select id="tbg_kode" class="form-select"></select></div>
                    <div class="col-3"><span class="form-label-sm">Lokasi/Alamat</span><input id="tbg_lokasi" class="form-control" placeholder="Lokasi/Alamat"></div>
                    <div class="col-1"><span class="form-label-sm">Luas Tanah</span><input id="tbg_luas_tanah" type="number" class="form-control" placeholder="Luas Tanah"></div>
                    <div class="col-1"><span class="form-label-sm">Luas Bangunan</span><input id="tbg_luas_bangun" type="number" class="form-control" placeholder="Luas Bangunan"></div>
                    <div class="col-1"><span class="form-label-sm">Th Perol</span><input id="tbg_th_perol" type="number" class="form-control" placeholder="Th Perol"></div>
                    <div class="col-2"><span class="form-label-sm">Harga Perolehan</span><input id="tbg_harga" class="form-control money" placeholder="Harga Perolehan" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Nilai Saat Ini</span><input id="tbg_nilai" class="form-control money" placeholder="Nilai Saat Ini" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Sertifikat</span><input id="tbg_sertifikat" class="form-control" placeholder="Sertifikat"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_harta_tidak_bergerak" onclick="submitForm(FORM_CONFIG.tidakbergerak)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="tbg_info" class="form-control" placeholder="Informasi Tambahan (opsional)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_harta_tidak_bergerak" onclick="cancelEdit(FORM_CONFIG.tidakbergerak)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:280px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Lokasi</th><th>Tanah</th><th>Bangunan</th><th>Th Perol</th><th class="text-end">Harga</th><th class="text-end">Nilai</th><th>Sertifikat</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelTidakBergerak"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="lainnya">
            <div class="card"><div class="card-header"><i class="bi bi-box-seam"></i>Harta Lainnya</div>
            <div class="card-body" id="form_harta_lainnya">
                <div class="row g-2">
                    <div class="col-3"><span class="form-label-sm">Kode</span><select id="lain_kode" class="form-select"></select></div>
                    <div class="col-1"><span class="form-label-sm">Th Perol</span><input id="lain_th_perol" type="number" class="form-control" placeholder="Th Perol"></div>
                    <div class="col-2"><span class="form-label-sm">Bukti Kepemilikan/No Akun</span><input id="lain_bukti" class="form-control" placeholder="Bukti Kepemilikan/No Akun"></div>
                    <div class="col-2"><span class="form-label-sm">Harga Perolehan</span><input id="lain_harga" class="form-control money" placeholder="Harga Perolehan" oninput="formatMoneyLive(this)"></div>
                    <div class="col-2"><span class="form-label-sm">Nilai Saat Ini</span><input id="lain_nilai" class="form-control money" placeholder="Nilai Saat Ini" oninput="formatMoneyLive(this)"></div>
                    <div class="col-1 d-flex align-items-end gap-2">
                        <button class="btn btn-primary" id="btn_harta_lainnya" onclick="submitForm(FORM_CONFIG.lainnya)">Simpan</button>
                    </div>
                </div>
                <div class="row g-2 mt-1">
                    <div class="col-12"><span class="form-label-sm">Informasi Tambahan</span><input id="lain_keterangan" class="form-control" placeholder="Informasi Tambahan (misal jenis/berat emas, nama merek)"></div>
                </div>
                <button class="btn btn-outline-secondary btn-sm btn-cancel-edit mt-2" id="cancel_harta_lainnya" onclick="cancelEdit(FORM_CONFIG.lainnya)">Batal Edit</button>
            </div></div>
            <div class="card"><div class="card-body" style="max-height:280px;overflow-y:auto;">
                <div class="table-responsive">
                <table class="table table-sm table-hover"><thead><tr><th>Kode</th><th>Deskripsi</th><th>Th Perol</th><th>Bukti Kepemilikan</th><th class="text-end">Harga</th><th class="text-end">Nilai</th><th>Info Tambahan</th><th>Aksi</th></tr></thead><tbody id="tabelLainnya"></tbody></table>
                </div>
            </div></div>
        </div>

        <div class="tab-pane" id="identitas">
            <div class="card"><div class="card-header"><i class="bi bi-person-vcard"></i>Data Wajib Pajak</div>
            <div class="card-body">
                <div class="row g-3">
                    <div class="col-md-6"><label class="form-label-sm">NIK</label><input id="identitas_nik" class="form-control"></div>
                    <div class="col-md-6"><label class="form-label-sm">NPWP</label><input id="identitas_npwp" class="form-control"></div>
                    <div class="col-md-6"><label class="form-label-sm">Nama</label><input id="identitas_nama" class="form-control"></div>
                    <div class="col-md-6"><label class="form-label-sm">Telepon</label><input id="identitas_telepon" class="form-control"></div>
                    <div class="col-md-6"><label class="form-label-sm">Email</label><input id="identitas_email" class="form-control"></div>
                    <div class="col-md-3"><label class="form-label-sm">Status Kawin</label><select id="identitas_status" class="form-select"><option value="TK">TK - Tidak Kawin</option><option value="K">K - Kawin</option></select></div>
                    <div class="col-md-3"><label class="form-label-sm">Status PTKP</label><select id="identitas_ptkp" class="form-select"></select></div>
                    <div class="col-12"><button class="btn btn-success" onclick="simpanIdentitas()"><i class="bi bi-check2"></i> Simpan Identitas</button></div>
                </div>
            </div></div>
        </div>
    </div>
    </main>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
const KODE_UTANG = [
    {kode:'UT001', desc:'Kartu Kredit'},
    {kode:'UT002', desc:'Utang Afiliasi'},
    {kode:'UT003', desc:'Utang Bank / Lembaga Keuangan (KPR, Leasing)'},
    {kode:'UT099', desc:'Utang Lainnya'}
];
const KODE_KAS = [
    {kode:'0101', desc:'Uang tunai/bank notes/koin'},
    {kode:'0102', desc:'Tabungan (Bank/Lembaga Keuangan)'},
    {kode:'0103', desc:'Deposito'},
    {kode:'0104', desc:'Giro'},
    {kode:'0105', desc:'Uang elektronik (e-money)'},
    {kode:'0106', desc:'Cek'},
    {kode:'0107', desc:'Wesel'},
    {kode:'0108', desc:'Commercial paper'},
    {kode:'0199', desc:'Setara kas lainnya'}
];
const KODE_PIUTANG = [
    {kode:'0201', desc:'Piutang Usaha'},
    {kode:'0202', desc:'Piutang Afiliasi'},
    {kode:'0299', desc:'Piutang Lainnya'}
];
const KODE_INVESTASI = [
    {kode:'0301', desc:'Saham yang dibeli untuk dijual kembali'},
    {kode:'0302', desc:'Saham Non Bursa'},
    {kode:'0303', desc:'Saham Bursa'},
    {kode:'0304', desc:'Obligasi Perusahaan'},
    {kode:'0305', desc:'Obligasi Pemerintah Indonesia'},
    {kode:'0306', desc:'Surat Utang Lainnya'},
    {kode:'0307', desc:'KIK / Reksa Dana'},
    {kode:'0308', desc:'Instrumen derivatif'},
    {kode:'0309', desc:'Penyertaan modal (bukan saham)'},
    {kode:'0310', desc:'Asuransi (murni/proteksi)'},
    {kode:'0311', desc:'Unit Link di Asuransi'},
    {kode:'0399', desc:'Investasi lainnya (Crypto, Trust Fund)'}
];
const KODE_BERGERAK = [
    {kode:'0401', desc:'Sepeda'}, {kode:'0402', desc:'Sepeda Motor'},
    {kode:'0403', desc:'Mobil Penumpang'}, {kode:'0404', desc:'Bus'},
    {kode:'0405', desc:'Kendaraan Angkutan Jalan'}, {kode:'0406', desc:'Kendaraan Tujuan Khusus'},
    {kode:'0407', desc:'Kereta'}, {kode:'0408', desc:'Pesawat Terbang'},
    {kode:'0409', desc:'Kapal'}, {kode:'0410', desc:'Mesin'},
    {kode:'0411', desc:'Gerobak'}, {kode:'0412', desc:'Kapal Pesiar'},
    {kode:'0499', desc:'Harta Bergerak Lainnya'}
];
const KODE_TIDAK_BERGERAK = [
    {kode:'0501', desc:'Tanah Kosong'},
    {kode:'0502', desc:'Tanah/Bangunan Tempat Tinggal'},
    {kode:'0503', desc:'Apartemen'},
    {kode:'0504', desc:'Tanah/Bangunan untuk Usaha/Disewakan'},
    {kode:'0599', desc:'Harta Tidak Bergerak Lainnya'}
];
const KODE_LAINNYA = [
    {kode:'0601', desc:'Paten'}, {kode:'0602', desc:'Royalti'},
    {kode:'0603', desc:'Merek dagang'}, {kode:'0699', desc:'Harta Tidak Berwujud Lainnya'},
    {kode:'0701', desc:'Emas batangan'}, {kode:'0702', desc:'Emas Perhiasan'},
    {kode:'0703', desc:'Perhiasan Non-Emas / Permata'},
    {kode:'0704', desc:'Barang seni dan antik'},
    {kode:'0799', desc:'Harta Lainnya (Perabot, Elektronik, Persediaan)'}
];
const KODE_FINAL = [
    {kode:'F401', desc:'Bunga Deposito/Tabungan/Diskonto SBI/Jasa Giro'},
    {kode:'F402', desc:'Bunga/Diskonto Obligasi'},
    {kode:'F403', desc:'Penjualan Saham di Bursa Efek'},
    {kode:'F404', desc:'Hadiah Undian'},
    {kode:'F405', desc:'Pesangon/Tunjangan Hari Tua/Tebusan Pensiun'},
    {kode:'F406', desc:'Honorarium Beban APBN/APBD'},
    {kode:'F407', desc:'Pengalihan Hak atas Tanah dan/atau Bangunan'},
    {kode:'F408', desc:'Persewaan Tanah dan/atau Bangunan'},
    {kode:'F409', desc:'Usaha Jasa Konstruksi'},
    {kode:'F410', desc:'Dividen Diinvestasikan Sesuai Ketentuan'},
    {kode:'F499', desc:'Penghasilan Final Lainnya'}
];
const KODE_BUKAN_OBJEK = [
    {kode:'N501', desc:'Bantuan/Sumbangan/Hibah'},
    {kode:'N502', desc:'Warisan'},
    {kode:'N503', desc:'Bagian Laba Firma/Persekutuan/Perkumpulan (bukan atas saham)'},
    {kode:'N504', desc:'Klaim Asuransi Kesehatan/Kecelakaan/Jiwa/Dwiguna/Beasiswa'},
    {kode:'N505', desc:'Beasiswa'},
    {kode:'N599', desc:'Bukan Objek Pajak Lainnya'}
];
const PTKP_OPTIONS = [
    {kode:'TK/0', label:'TK/0 - Rp 54.000.000'}, {kode:'TK/1', label:'TK/1 - Rp 58.500.000'},
    {kode:'TK/2', label:'TK/2 - Rp 63.000.000'}, {kode:'TK/3', label:'TK/3 - Rp 67.500.000'},
    {kode:'K/0', label:'K/0 - Rp 58.500.000'}, {kode:'K/1', label:'K/1 - Rp 63.000.000'},
    {kode:'K/2', label:'K/2 - Rp 67.500.000'}, {kode:'K/3', label:'K/3 - Rp 72.000.000'}
];

// Basis pengetahuan klasifikasi transaksi -> kategori pajak. Dirangkum dari berbagai
// sumber (DJP, Ortax, DDTC, Klikpajak, dll, per Agustus 2026). Panduan umum, bukan
// nasihat pajak resmi - kasus besar/tidak biasa tetap perlu dikonsultasikan ke AR pajak.
const KNOWLEDGE_BASE = [
    { keywords:['bibit','reksadana','reksa dana','bareksa','ajaib reksadana','sbn ritel bibit','reksa dana pasar uang','rdpu'],
      judul:'Investasi Reksa Dana (Bibit/Bareksa/Ajaib)', masuk_tab:'Harta > Investasi (kode 0307)',
      penjelasan:'Deposit/pembelian reksa dana BUKAN penghasilan - ini cuma memindahkan uang dari kas ke bentuk investasi.',
      pajak_tambahan:'Keuntungan dari kenaikan Nilai Aktiva Bersih (NAB)/capital gain saat redemption BUKAN objek pajak bagi investor individu - pajak sudah dikenakan di level produk oleh manajer investasi. Tidak perlu dihitung ulang, cukup dilaporkan sebagai "penghasilan tidak termasuk objek pajak".',
      cara_isi:['Tab: Harta > Investasi', 'Kode: 0307 - KIK / Reksa Dana', 'Institusi: nama platform (misal Bibit, Bareksa, Ajaib)',
        'No Akun: nomor akun/CIF investasi kamu di platform tsb', 'Harga Perolehan: total uang yang sudah disetor untuk beli unit',
        'Nilai Saat Ini: nilai unit penyertaan (NAB/unit x jumlah unit) per 31 Desember'] },
    { keywords:['beli saham','jual saham','saham bursa','ajaib saham','stockbit','ipot','mirae','mnc sekuritas','trading saham','main saham'],
      judul:'Jual/Beli Saham di Bursa', masuk_tab:'Harta > Investasi (kode 0303)',
      penjelasan:'Beli saham = pindah kas jadi harta investasi, bukan penghasilan.',
      pajak_tambahan:'Saat JUAL: capital gain sudah kena PPh Final 0,1% dari nilai transaksi jual, dipotong otomatis oleh sekuritas/bursa saat itu juga - tidak perlu dihitung ulang.',
      cara_isi:['Tab: Harta > Investasi', 'Kode: 0303 - Saham Bursa', 'Institusi: nama sekuritas (misal Ajaib, Stockbit, IPOT)',
        'No Akun: nomor SID/RDN kamu', 'Harga Perolehan: total harga beli semua saham yang masih dipegang',
        'Nilai Saat Ini: harga penutupan saham x jumlah lembar per 31 Desember'] },
    { keywords:['dividen','deviden','dapat dividen','terima dividen'],
      judul:'Dividen Saham', masuk_tab:'Penghasilan Lain > Final (kode F410)',
      penjelasan:'Dividen yang diterima dari saham perusahaan dalam negeri.',
      pajak_tambahan:'PPh Final 10%, KECUALI diinvestasikan lagi ke instrumen dalam negeri (SBN, deposito, saham, dll) paling lambat akhir bulan ke-3 setelah tahun diterima, dan ditahan minimal 3 tahun pajak berturut-turut - baru bebas pajak (wajib lapor realisasi investasi).',
      cara_isi:['Tab: Penghasilan Lain > Final', 'Kode: F410 - Dividen Diinvestasikan Sesuai Ketentuan',
        'Jumlah Bruto: total dividen diterima setahun', 'PPh Final Dibayar: 10% dari bruto (0 kalau bebas pajak karena diinvestasikan ulang)'] },
    { keywords:['deposito'],
      judul:'Deposito Bank', masuk_tab:'Harta > Kas (kode 0103) + Penghasilan Lain > Final untuk bunganya',
      penjelasan:'Pokok deposito dicatat di Kas. Bunga yang diterima setahun dicatat terpisah di Penghasilan Lain > Final.',
      pajak_tambahan:'Bunga deposito kena PPh Final 20%, sudah dipotong otomatis oleh bank saat pencairan bunga.',
      cara_isi:['Pokok -> Tab Harta > Kas, Kode 0103 - Deposito, Saldo = nilai pokok per 31 Desember',
        'Bunga -> Tab Penghasilan Lain > Final, Kode F401, Jumlah Bruto = total bunga setahun, PPh Final = 20% dari bunga'] },
    { keywords:['tabungan','giro','rekening'],
      judul:'Tabungan/Giro Bank', masuk_tab:'Harta > Kas (kode 0101-0104)',
      penjelasan:'Saldo tabungan/giro per 31 Desember dicatat sebagai Kas. Ini bukan penghasilan, cuma posisi harta.',
      pajak_tambahan:'Kalau ada bunga/jasa giro yang diterima (biasanya kecil), sudah kena PPh Final 20% dan dipotong otomatis bank.',
      cara_isi:['Tab: Harta > Kas', 'Kode: 0101 (tunai) / 0102 (tabungan) / 0104 (giro)', 'Nama Bank & No Rekening: sesuai rekening kamu',
        'Saldo: saldo akhir per 31 Desember (cek mutasi/e-statement)'] },
    { keywords:['emas','emas digital','antam','pegadaian','logam mulia','pluang emas','tokopedia emas','shopee emas','dana emas','cicil emas','tabungan emas','emas online'],
      judul:'Emas Batangan/Perhiasan/Digital (Antam, Pegadaian, Pluang, Tokopedia Emas, dll)', masuk_tab:'Harta > Lainnya (kode 0701/0702)',
      penjelasan:'Emas fisik dan emas digital (Pluang, Tokopedia Emas, Pegadaian Digital, dll) diperlakukan SAMA - keduanya representasi kepemilikan emas, dicatat sebagai harta.',
      pajak_tambahan:'Kepemilikan emas per 31 Desember tidak kena pajak, cukup dilaporkan sebagai harta. TAPI kalau emas DIJUAL dengan untung, keuntungannya (selisih jual-beli) dianggap "penghasilan lain-lain/kenaikan kekayaan bersih" yang digabung dengan penghasilan lain dan kena tarif PPh progresif (bukan final) - beda dari saham/kripto.',
      catatan:'Aplikasi ini belum ada tab khusus untuk keuntungan penjualan emas - kalau tahun ini kamu jual emas untung, catat dulu di Catatan Penghasilan.',
      cara_isi:['Tab: Harta > Lainnya', 'Kode: 0701 - Emas batangan (atau 0702 - Emas Perhiasan)',
        'Bukti Kepemilikan/No Akun: nomor sertifikat emas fisik, atau ID akun aplikasi (misal akun Pluang/Tokopedia Emas)',
        'Harga Perolehan: total rupiah yang sudah disetor untuk beli emas',
        'Nilai Saat Ini: berat emas (gram) x harga buyback per gram pada 31 Desember',
        'Informasi Tambahan: nama platform/toko, misal "Emas digital di Pluang"'] },
    { keywords:['kripto','crypto','bitcoin','ethereum','indodax','pintu','tokocrypto','binance','koin','nft','trading kripto','jual kripto','beli kripto'],
      judul:'Aset Kripto (Bitcoin/Crypto/NFT)', masuk_tab:'Harta > Investasi (kode 0399)',
      penjelasan:'Kripto (termasuk NFT) yang masih dipegang per 31 Desember wajib dicatat sebagai harta investasi.',
      pajak_tambahan:'Transaksi jual/tukar kripto kena PPh Final 0,21% dari NILAI TRANSAKSI (bukan dari untungnya), dipotong otomatis exchange terdaftar. Kerugian (capital loss) TIDAK bisa dikompensasikan ke penghasilan lain.',
      cara_isi:['Tab: Harta > Investasi', 'Kode: 0399 - Investasi lainnya (Crypto, Trust Fund)', 'Institusi: nama exchange (misal Indodax, Pintu, Tokocrypto)',
        'No Akun: user ID/alamat wallet kamu', 'Harga Perolehan: total rupiah yang dipakai beli koin yang masih dipegang',
        'Nilai Saat Ini: harga pasar koin x jumlah koin per 31 Desember'] },
    { keywords:['tanah','rumah','properti','apartemen','ruko','beli rumah','beli tanah'],
      judul:'Beli Tanah/Rumah/Properti', masuk_tab:'Harta > Tidak Bergerak',
      penjelasan:'Catat sebagai harta: Harga Perolehan = harga beli di akta jual-beli, Nilai Saat Ini = perkiraan nilai pasar sekarang.',
      catatan:'Saat BELI ada BPHTB (~5% dari nilai transaksi, dibayar ke Pemda) - ini di luar SPT PPh Tahunan, jadi tidak perlu dicatat di sini.',
      cara_isi:['Tab: Harta > Tidak Bergerak', 'Kode: sesuai jenis (0502 rumah tinggal, 0503 apartemen, dst)', 'Lokasi/Alamat: alamat lengkap properti',
        'Harga Perolehan: harga di akta jual-beli', 'Nilai Saat Ini: NJOP terbaru atau estimasi harga pasar', 'Sertifikat: SHM/HGB/dll'] },
    { keywords:['jual rumah','jual tanah','jual properti','pengalihan tanah','jual bangunan'],
      judul:'Jual Tanah/Rumah/Bangunan', masuk_tab:'Penghasilan Lain > Final (kode F407)',
      penjelasan:'Penghasilan dari penjualan/pengalihan hak atas tanah dan bangunan.',
      pajak_tambahan:'PPh Final 2,5% dari nilai bruto (harga jual atau NJOP, mana yang lebih tinggi), dibayar SENDIRI sebelum akta ditandatangani notaris/PPAT. Kalau ini dari warisan, bisa ajukan SKB (Surat Keterangan Bebas) supaya tidak dipotong.',
      cara_isi:['Tab: Penghasilan Lain > Final', 'Kode: F407 - Pengalihan Hak atas Tanah dan/atau Bangunan',
        'Jumlah Bruto: harga jual atau NJOP (mana yang lebih tinggi)', 'PPh Final Dibayar: 2,5% dari Jumlah Bruto',
        'Jangan lupa: hapus/kurangi harta ini dari tab Tidak Bergerak karena sudah tidak dimiliki lagi'] },
    { keywords:['hibah','dikasih orang tua','pemberian orang tua'],
      judul:'Hibah Diterima', masuk_tab:'Penghasilan Lain > Bukan Objek (kode N501)',
      penjelasan:'Harta/uang yang diberikan tanpa imbalan (hibah).',
      pajak_tambahan:'BEBAS pajak HANYA jika: (1) dari keluarga sedarah garis lurus SATU DERAJAT (orang tua kandung <-> anak kandung), ATAU dari badan keagamaan/pendidikan/sosial/UMKM tertentu, DAN (2) TIDAK ada hubungan usaha/pekerjaan/kepemilikan antara pemberi-penerima. Di luar itu (misal dari saudara kandung, sepupu, teman, atau ada hubungan bisnis), hibah dianggap penghasilan biasa dan kena PPh tarif progresif.',
      cara_isi:['Tab: Penghasilan Lain > Bukan Objek', 'Kode: N501 - Bantuan/Sumbangan/Hibah', 'Jumlah: nilai harta/uang yang diterima',
        'Informasi Tambahan: dari siapa dan hubungannya (penting untuk pembuktian syarat bebas pajak)'] },
    { keywords:['warisan','waris','peninggalan','warisan uang','warisan tunai'],
      judul:'Warisan Diterima', masuk_tab:'Penghasilan Lain > Bukan Objek (kode N502)',
      penjelasan:'Harta yang diterima dari almarhum/almarhumah sebagai ahli waris.',
      pajak_tambahan:'BEBAS pajak asal harta warisan sudah dilaporkan di SPT pewaris (atau penghasilan pewaris dulu di bawah PTKP), dan pajak terutang pewaris (kalau ada) sudah lunas. Kalau warisan berupa tanah/bangunan, ajukan SKB PPh supaya tidak kena potong PPh final pengalihan 2,5%.',
      cara_isi:['Tab: Penghasilan Lain > Bukan Objek', 'Kode: N502 - Warisan', 'Jumlah: total nilai warisan yang diterima',
        'Informasi Tambahan: nama pewaris dan hubungan keluarga', 'Kalau warisan berupa harta (properti/kendaraan), catat juga di tab Harta yang sesuai'] },
    { keywords:['thr','tunjangan hari raya','bonus kantor','bonus tahunan'],
      judul:'THR / Bonus dari Kantor', masuk_tab:'Pekerjaan (sudah termasuk di Bruto)',
      penjelasan:'THR dan bonus dari pemberi kerja biasanya SUDAH termasuk dalam kolom "Penghasilan Bruto" di bukti potong 1721-A1 - tidak perlu dicatat terpisah.',
      catatan:'Pastikan saja Total Bruto yang kamu input di tab Pekerjaan memang sudah mencakup THR & bonus setahun sesuai 1721-A1.',
      cara_isi:['Tidak perlu input terpisah - pastikan sudah termasuk di field Penghasilan Bruto tab Pekerjaan'] },
    { keywords:['pesangon','phk','di-phk','berhenti kerja','pemutusan hubungan kerja'],
      judul:'Pesangon (PHK)', masuk_tab:'Penghasilan Lain > Final (kode F405)',
      penjelasan:'Uang pesangon yang diterima saat berhenti/diberhentikan dari pekerjaan.',
      pajak_tambahan:'PPh Final tarif berlapis: 0% (s.d Rp50 juta), 5% (Rp50-100 juta), 15% (Rp100-500 juta), 25% (di atas Rp500 juta) - biasanya sudah dipotong pemberi kerja.',
      cara_isi:['Tab: Penghasilan Lain > Final', 'Kode: F405 - Pesangon, Tunjangan Hari Tua, Tebusan Pensiun', 'Jumlah Bruto: total pesangon diterima',
        'PPh Final Dibayar: sesuai tarif berlapis, biasanya sudah tertera di bukti potong dari HR'] },
    { keywords:['freelance','honor','proyek sampingan','jasa desain','kerja lepas','side job','sampingan','penghasilan tambahan'],
      judul:'Freelance / Honor / Proyek Sampingan', masuk_tab:'Belum ada tab khusus - catat dulu di Catatan Penghasilan',
      penjelasan:'Penghasilan dari pekerjaan bebas/jasa di luar gaji tetap. Aplikasi ini fokus untuk karyawan (1721-A1), jadi untuk pekerjaan bebas belum ada tab dedicated.',
      pajak_tambahan:'Kena PPh progresif seperti gaji, dihitung pakai Norma Penghitungan Penghasilan Neto (NPPN, persentase dari omzet, kalau omzet setahun <Rp4,8 miliar) atau pembukuan. Kalau klien memotong PPh 21/23 saat bayar, itu jadi kredit pajak - catat brutonya juga.',
      cara_isi:['Sementara -> Tab Catatan Penghasilan: Deskripsi = nama proyek/klien, Perkiraan Jumlah = nilai honor, Kategori = "Pekerjaan"',
        'Saat isi SPT resmi: hitung penghasilan neto pakai NPPN, gabungkan ke total penghasilan kena pajak progresif'] },
    { keywords:['sewa rumah','sewa ruko','sewa tanah','disewakan','kontrakan','sewa gudang'],
      judul:'Sewa Rumah/Ruko/Tanah', masuk_tab:'Penghasilan Lain > Final (kode F408)',
      penjelasan:'Penghasilan dari menyewakan tanah dan/atau bangunan (rumah kontrakan, ruko, gudang, dll).',
      pajak_tambahan:'PPh Final 10% dari nilai bruto sewa. Kalau penyewa bukan pemotong pajak (perorangan biasa), KAMU (pemilik) wajib setor sendiri PPh Final-nya lewat Coretax.',
      cara_isi:['Tab: Penghasilan Lain > Final', 'Kode: F408 - Persewaan Tanah dan/atau Bangunan',
        'Jumlah Bruto: total nilai sewa setahun (termasuk biaya layanan/perawatan kalau ditanggung penyewa)',
        'PPh Final Dibayar: 10% dari Jumlah Bruto (setor sendiri kalau penyewa perorangan)'] },
    { keywords:['kos','kos-kosan','kosan','sewa kamar','asrama'],
      judul:'Sewa Kos-Kosan', masuk_tab:'Penghasilan Lain > Final (kode F408), dengan pengecualian',
      penjelasan:'Rumah kos/kamar sewa untuk mahasiswa/pekerja.',
      pajak_tambahan:'DIKECUALIKAN dari PPh Final sewa tanah/bangunan (PP 34/2017 Pasal 2 ayat 3) karena dianggap jasa akomodasi, bukan sewa murni. Kalau omzetnya besar & rutin, bisa masuk kategori usaha biasa - sebaiknya konsultasi AR pajak kalau kos-nya sudah besar.',
      cara_isi:['Kalau kecil/sampingan: cukup dicatat sebagai harta properti di tab Tidak Bergerak, penghasilannya tidak wajib dipotong PPh final',
        'Kalau usaha kos besar & rutin: konsultasi AR pajak untuk skema yang tepat'] },
    { keywords:['hadiah undian','menang undian','giveaway','doorprize'],
      judul:'Hadiah Undian/Giveaway', masuk_tab:'Penghasilan Lain > Final (kode F404)',
      penjelasan:'Hadiah dari undian resmi (bank, promo, giveaway berhadiah).',
      pajak_tambahan:'PPh Final 25% dari nilai hadiah, biasanya sudah dipotong penyelenggara sebelum hadiah diserahkan.',
      cara_isi:['Tab: Penghasilan Lain > Final', 'Kode: F404 - Hadiah Undian', 'Jumlah Bruto: nilai hadiah', 'PPh Final Dibayar: 25% dari nilai hadiah'] },
    { keywords:['klaim asuransi','asuransi kesehatan','asuransi jiwa','asuransi kecelakaan','santunan asuransi'],
      judul:'Klaim Asuransi', masuk_tab:'Penghasilan Lain > Bukan Objek (kode N504)',
      penjelasan:'Uang penggantian/klaim dari perusahaan asuransi (kesehatan, jiwa, kecelakaan, dwiguna, beasiswa).',
      pajak_tambahan:'Tidak ada pajak tambahan - ini murni penggantian kerugian/risiko, bukan penghasilan baru.',
      cara_isi:['Tab: Penghasilan Lain > Bukan Objek', 'Kode: N504 - Klaim Asuransi Kesehatan/Kecelakaan/Jiwa/Dwiguna/Beasiswa', 'Jumlah: nilai klaim yang diterima'] },
    { keywords:['beasiswa'],
      judul:'Beasiswa Diterima', masuk_tab:'Penghasilan Lain > Bukan Objek (kode N505)',
      penjelasan:'Dana beasiswa untuk pendidikan.',
      pajak_tambahan:'BEBAS pajak kalau diberikan tanpa hubungan istimewa dengan pemberi, dan digunakan untuk pendidikan formal/nonformal terstruktur di dalam negeri.',
      cara_isi:['Tab: Penghasilan Lain > Bukan Objek', 'Kode: N505 - Beasiswa', 'Jumlah: total dana beasiswa diterima'] },
    { keywords:['kartu kredit','kpr','kta','kredit tanpa agunan','cicilan','leasing','pinjaman bank'],
      judul:'Utang Kartu Kredit/KPR/KTA (dari Bank/Lembaga Resmi)', masuk_tab:'Utang',
      penjelasan:'Sisa utang yang belum lunas per 31 Desember, dari bank atau lembaga keuangan resmi.',
      pajak_tambahan:'Tidak ada pajak langsung dari berutang. Catatan: bunga yang KAMU BAYAR atas utang pribadi tidak bisa jadi pengurang pajak (beda dengan utang usaha).',
      cara_isi:['Tab: Utang', 'Kode: UT001 (kartu kredit) / UT003 (KPR/leasing)', 'Nama Kreditor: nama bank/leasing',
        'Jumlah Utang: sisa pokok yang belum lunas per 31 Desember', 'Tahun Peminjaman: tahun pertama kali ambil kredit'] },
    { keywords:['utang ke bos','utang ke teman','utang ke saudara','utang ke orang tua','pinjam uang','pinjam duit','minjem duit','minjem uang','dipinjami','utang pribadi','utang perorangan','ngutang','utang teman','utang saudara'],
      judul:'Utang ke Perorangan (Bos/Teman/Saudara/Orang Tua)', masuk_tab:'Utang (kode UT099 - Utang Lainnya)',
      penjelasan:'Uang yang kamu pinjam dari perorangan (bukan bank/lembaga resmi) - misal dari bos, teman, saudara, atau orang tua.',
      pajak_tambahan:'Tidak ada pajak langsung buat kamu sebagai peminjam. Kalau pemberi pinjaman mengenakan bunga, bunga itu jadi PENGHASILAN bagi si pemberi pinjaman (dia yang perlu lapor, bukan kamu).',
      cara_isi:['Tab: Utang', 'Kode: UT099 - Utang Lainnya', 'Nama Kreditor: nama orang yang meminjamkan (bos/teman/saudara/orang tua)',
        'Jumlah Utang: sisa utang yang belum dibayar per 31 Desember', 'Informasi Tambahan: hubungan dengan pemberi pinjaman dan alasan pinjam'] },
    { keywords:['p2p','pinjol','peer to peer','investree','koinworks','modalku','danain','pendanaan','jadi lender'],
      judul:'P2P Lending (sebagai pemberi dana/lender)', masuk_tab:'Piutang (pokok) + belum ada tab untuk bunganya',
      penjelasan:'Kalau kamu jadi pemberi dana (lender) di platform P2P lending resmi (terdaftar OJK), pokok yang dipinjamkan dicatat di tab Piutang.',
      pajak_tambahan:'Bunga yang kamu terima kena PPh Pasal 23 15% (dipotong platform P2P) - ini TIDAK final, jadi harus digabung dengan penghasilan lain dan dihitung ulang pakai tarif progresif saat lapor SPT (PPh yang dipotong jadi kredit pajak).',
      catatan:'Aplikasi ini belum ada tab khusus "penghasilan lainnya digabung" - sementara catat di Catatan Penghasilan supaya tidak lupa.',
      cara_isi:['Pokok -> Tab Piutang, Kode 0299, Nama Penerima = nama platform/peminjam, Nilai & Saldo Piutang = sisa dana belum kembali',
        'Bunga -> catat dulu di Catatan Penghasilan (bukan final, digabung progresif)'] },
    { keywords:['meminjamkan uang','pinjamin duit','pinjamin uang','ngasih pinjaman','kasih pinjam','piutang teman','piutang saudara'],
      judul:'Meminjamkan Uang ke Teman/Saudara (Piutang Pribadi)', masuk_tab:'Piutang (kode 0299 - Piutang Lainnya)',
      penjelasan:'Uang yang kamu pinjamkan ke orang lain (bukan lewat platform P2P resmi) - kamu jadi punya piutang ke orang tersebut.',
      pajak_tambahan:'Tidak ada pajak langsung selama tidak ada bunga. Kalau kamu kenakan bunga, bunga yang kamu terima itu PENGHASILAN buat kamu dan kena PPh progresif - catat di Catatan Penghasilan karena app belum ada tab khusus untuk ini.',
      cara_isi:['Tab: Piutang', 'Kode: 0299 - Piutang Lainnya', 'Nama Penerima: nama orang yang kamu pinjami',
        'Nilai Piutang: jumlah awal yang dipinjamkan', 'Saldo Piutang: sisa yang belum dikembalikan per 31 Desember'] },
    { keywords:['gadai','pegadaian gadai','gadai emas','gadai bpkb','menggadaikan'],
      judul:'Menggadaikan Barang (Pegadaian)', masuk_tab:'Utang (kode UT099) - barang yang digadaikan tetap dicatat di Harta',
      penjelasan:'Uang yang kamu terima dari menggadaikan barang (emas, BPKB, dll) BUKAN penghasilan - itu pinjaman dengan jaminan barang.',
      pajak_tambahan:'Tidak ada pajak tambahan. Barang yang digadaikan tetap kamu miliki secara hukum, jadi tetap dicatat di tab Harta yang sesuai (misal emas di Harta Lainnya) - JANGAN dihapus dari daftar harta.',
      cara_isi:['Tab: Utang, Kode UT099 - Utang Lainnya', 'Nama Kreditor: "Pegadaian" atau nama lembaga gadai',
        'Jumlah Utang: sisa pinjaman gadai yang belum ditebus', 'Barang yang digadaikan: tetap dicatat di tab Harta yang sesuai'] },
    { keywords:['cashback','reward','poin','promo'],
      judul:'Cashback / Reward Promo', masuk_tab:'Umumnya tidak perlu dicatat terpisah',
      penjelasan:'Cashback kecil dari e-commerce/e-wallet/kartu kredit.',
      pajak_tambahan:'Untuk nilai kecil & tidak rutin, umumnya tidak material dan tidak perlu dilaporkan terpisah. Kalau nilainya besar & rutin (misal komisi afiliasi/reseller aktif), sebaiknya diperlakukan sebagai penghasilan usaha/freelance.',
      cara_isi:['Tidak perlu dicatat kalau nilainya kecil. Kalau rutin & besar, perlakukan seperti Freelance (catat di Catatan Penghasilan).'] },
    { keywords:['zakat','sumbangan keagamaan','infak','sedekah wajib'],
      judul:'Zakat / Sumbangan Keagamaan Wajib (yang kamu BAYAR)', masuk_tab:'Penghasilan Lain > Zakat',
      penjelasan:'Zakat penghasilan yang kamu bayarkan lewat lembaga resmi.',
      pajak_tambahan:'Mengurangi penghasilan neto SEBELUM dihitung PTKP dan PPh - jadi mengurangi pajak terutang. Syarat: harus lewat lembaga amil zakat/keagamaan resmi yang disahkan pemerintah (misal BAZNAS).',
      cara_isi:['Tab: Penghasilan Lain > Zakat', 'Deskripsi: jenis zakat (misal "Zakat Penghasilan")',
        'Lembaga Penerima: nama lembaga resmi (misal BAZNAS)', 'Jumlah: total zakat yang dibayar setahun'] },
    { keywords:['motor','mobil','kendaraan','beli motor','beli mobil'],
      judul:'Beli Kendaraan Bermotor', masuk_tab:'Harta > Bergerak',
      penjelasan:'Catat sebagai harta: Harga Perolehan = harga beli, Nilai Saat Ini = perkiraan harga jual sekarang.',
      catatan:'BBNKB (bea balik nama kendaraan, ke Pemda) di luar SPT PPh Tahunan, tidak perlu dicatat di sini.',
      cara_isi:['Tab: Harta > Bergerak', 'Kode: sesuai jenis (0402 motor, 0403 mobil, dst)', 'Merk/Model & No Polisi',
        'Harga Perolehan: harga beli', 'Nilai Saat Ini: estimasi harga jual sekarang (cek harga pasaran bekas)'] },
    { keywords:['unit link','asuransi investasi'],
      judul:'Asuransi Unit Link', masuk_tab:'Harta > Investasi (kode 0311)',
      penjelasan:'Produk asuransi yang digabung dengan investasi.',
      pajak_tambahan:'Catat sebagai harta investasi. Bagian premi murni asuransi umumnya tidak dianggap penghasilan/pengeluaran kena pajak.',
      cara_isi:['Tab: Harta > Investasi', 'Kode: 0311 - Unit Link di Asuransi', 'Institusi: nama perusahaan asuransi',
        'Harga Perolehan: total premi yang sudah dibayar', 'Nilai Saat Ini: nilai tunai polis (cek laporan tahunan asuransi)'] },
    { keywords:['obligasi','sbn','sukuk','sukuk ritel','obligasi ritel indonesia'],
      judul:'Obligasi / SBN / Sukuk Ritel', masuk_tab:'Harta > Investasi (kode 0304/0305)',
      penjelasan:'Surat utang pemerintah/korporasi yang kamu beli.',
      pajak_tambahan:'Kupon/bunga yang diterima kena PPh Final 10% (untuk obligasi pemerintah), biasanya sudah dipotong otomatis - opsional dicatat juga di Penghasilan Lain > Final (kode F402).',
      cara_isi:['Tab: Harta > Investasi', 'Kode: 0304 (obligasi korporasi) / 0305 (SBN pemerintah)', 'Institusi: penerbit/platform beli (misal Bibit untuk SBN ritel)',
        'Harga Perolehan: nilai nominal yang dibeli', 'Nilai Saat Ini: nilai pasar/nominal per 31 Desember'] },
    { keywords:['gaji','gaji bulanan','gaji pokok'],
      judul:'Gaji Bulanan dari Kantor', masuk_tab:'Pekerjaan',
      penjelasan:'Penghasilan rutin dari pemberi kerja tetap.',
      pajak_tambahan:'Sudah tercatat lengkap di bukti potong 1721-A1 dari kantor (bruto setahun + PPh 21 yang dipotong) - tinggal salin ke tab Pekerjaan.',
      cara_isi:['Tab: Pekerjaan', 'Nama & NPWP Pemberi Kerja: sesuai 1721-A1', 'Penghasilan Bruto: total gaji setahun sebelum potongan (dari 1721-A1)',
        'PPh Dipotong: PPh 21 yang sudah dipotong kantor (dari 1721-A1)'] },
    { keywords:['reimbursement','ganti biaya','uang dinas','penggantian biaya'],
      judul:'Reimbursement/Penggantian Biaya Kantor', masuk_tab:'Umumnya tidak perlu dicatat sebagai penghasilan',
      penjelasan:'Uang pengganti biaya yang sudah kamu keluarkan dulu untuk kerja (misal biaya dinas, transport).',
      pajak_tambahan:'Umumnya BUKAN objek pajak selama benar-benar penggantian biaya riil (reimbursement), bukan tunjangan tetap bulanan.',
      cara_isi:['Umumnya tidak perlu dicatat sebagai penghasilan/harta terpisah.'] },
    { keywords:['santunan','uang duka','bantuan sosial','bansos'],
      judul:'Santunan/Bantuan Sosial', masuk_tab:'Penghasilan Lain > Bukan Objek (kode N599)',
      penjelasan:'Bantuan/santunan dari pemerintah atau lembaga sosial resmi.',
      pajak_tambahan:'Tidak ada pajak tambahan untuk bantuan sosial resmi dari pemerintah/lembaga sosial.',
      cara_isi:['Tab: Penghasilan Lain > Bukan Objek', 'Kode: N599 - Bukan Objek Pajak Lainnya', 'Jumlah: nilai bantuan yang diterima'] },
    { keywords:['modal usaha','buka usaha','modal bisnis','buka toko','buka warung'],
      judul:'Modal untuk Usaha Sendiri', masuk_tab:'Bukan penghasilan - hasil usahanya nanti masuk penghasilan usaha/pekerjaan bebas',
      penjelasan:'Uang yang kamu pakai sebagai modal usaha sendiri bukan penghasilan/pengeluaran yang dilaporkan terpisah - itu perpindahan bentuk harta.',
      pajak_tambahan:'Penghasilan NETO dari usaha (omzet dikurangi biaya, atau pakai NPPN) kena PPh progresif digabung penghasilan lain. App ini belum ada tab usaha - catat dulu di Catatan Penghasilan.',
      cara_isi:['Catat perkembangan usaha di Catatan Penghasilan dulu', 'Aset usaha (kas usaha, inventaris) bisa dicatat di tab Harta yang sesuai kalau signifikan'] },
    { keywords:['youtube','adsense','konten kreator','endorse','endorsement','afiliasi','reseller','dropship','komisi affiliate','paid promote','tiktok shop','shopee affiliate','content creator'],
      judul:'Penghasilan YouTube/Konten Kreator/Endorse/Afiliasi', masuk_tab:'Belum ada tab khusus - mirip Freelance, catat dulu di Catatan Penghasilan',
      penjelasan:'Penghasilan dari platform digital (AdSense, endorse, komisi afiliasi, reseller/dropship) dianggap penghasilan usaha/pekerjaan bebas.',
      pajak_tambahan:'Kena PPh progresif seperti freelance, dihitung pakai Norma Penghitungan Penghasilan Neto kalau omzet <Rp4,8 miliar/tahun. Kalau ada pemotongan pajak dari platform/brand (PPh 21/23), itu jadi kredit pajak.',
      cara_isi:['Sementara -> Tab Catatan Penghasilan: Deskripsi = platform/brand, Perkiraan Jumlah = total pendapatan, Kategori = "Pekerjaan"',
        'Kumpulkan bukti potong (kalau ada) dari brand/platform yang memotong pajak'] },
    { keywords:['uang saku','kiriman orang tua','dikirim orang tua','uang bulanan dari orang tua','biaya hidup dari orang tua'],
      judul:'Uang Saku/Kiriman Rutin dari Orang Tua', masuk_tab:'Penghasilan Lain > Bukan Objek (kode N501, sama seperti hibah)',
      penjelasan:'Uang rutin yang dikirim orang tua kandung untuk biaya hidup (masih ditanggung).',
      pajak_tambahan:'BEBAS pajak karena termasuk hibah dari keluarga sedarah garis lurus satu derajat (orang tua kandung), asal tidak ada hubungan usaha/pekerjaan di antara kalian.',
      cara_isi:['Tab: Penghasilan Lain > Bukan Objek', 'Kode: N501', 'Jumlah: total kiriman setahun'] },
    { keywords:['kiriman uang dari teman','transfer dari teman','kiriman dari luar negeri','transfer luar negeri','uang dari teman','dikirim teman','remitansi','transfer masuk dari luar negeri','uang masuk dari luar negeri','kiriman uang','transfer dari saudara jauh'],
      judul:'Kiriman/Transfer Uang dari Teman atau Kerabat Jauh (Dalam/Luar Negeri)',
      masuk_tab:'Kemungkinan besar BUKAN Bukan-Objek - lihat penjelasan, kasus ini abu-abu tergantung tujuannya',
      penjelasan:'Beda dengan kiriman dari ORANG TUA KANDUNG (bebas pajak sebagai hibah keluarga sedarah), kiriman dari teman/kerabat jauh/pihak lain TIDAK otomatis bebas pajak. Pengecualian hibah bebas pajak hanya berlaku untuk keluarga sedarah garis lurus SATU DERAJAT (orang tua <-> anak kandung) atau badan keagamaan/pendidikan/sosial/UMKM tertentu - teman, saudara jauh (sepupu, om/tante, dst) TIDAK termasuk dalam pengecualian ini.',
      pajak_tambahan:'Kalau ini murni hadiah/pemberian cuma-cuma dari teman, secara aturan umum dianggap "tambahan kemampuan ekonomis" yang jadi OBJEK PAJAK dan kena PPh tarif progresif (digabung penghasilan lain). TAPI kalau sebenarnya ini pengembalian utang/piutang yang dulu kamu berikan, itu BUKAN penghasilan sama sekali. Kalau dari luar negeri, cek juga apakah sudah kena potong pajak di negara asal - itu berpotensi jadi kredit pajak luar negeri (PPh Pasal 24).',
      catatan:'Ini kasus abu-abu yang sangat tergantung konteks (tujuan pengiriman, hubungan dengan pengirim, rutin atau sekali). Transfer dari luar negeri juga sering otomatis dilaporkan ke DJP lewat pertukaran data antar-negara (AEOI/CRS), jadi sebaiknya jangan diabaikan. App ini belum ada tab untuk penghasilan lain-lain semacam ini - sangat disarankan konsultasi ke AR pajak/konsultan untuk kepastian.',
      cara_isi:['Kalau ternyata pengembalian piutang: cukup kurangi/hapus dari tab Piutang (kalau sebelumnya dicatat di sana), tidak perlu dicatat sebagai penghasilan',
        'Kalau ternyata hadiah/pemberian murni dari teman: catat dulu di Catatan Penghasilan dengan keterangan lengkap (dari siapa, tujuan), lalu konsultasikan ke AR pajak untuk kepastian perlakuan dan tarifnya',
        'Kalau dari luar negeri dan sudah kena potong pajak di sana: simpan bukti potongnya, kemungkinan bisa jadi kredit pajak luar negeri (PPh 24)'] },
    { keywords:['take over kpr','oper kredit','over kredit rumah'],
      judul:'Take Over/Oper Kredit KPR', masuk_tab:'Utang (kode UT003) - properti tetap dicatat di Harta Tidak Bergerak',
      penjelasan:'Mengambil alih sisa cicilan KPR dari orang lain.',
      pajak_tambahan:'Catat sisa pokok kredit sebagai Utang ke bank pemberi KPR. Properti yang di-take over dicatat sebagai Harta Tidak Bergerak dengan Harga Perolehan = harga take over.',
      cara_isi:['Tab Utang: Kode UT003, Nama Kreditor = nama bank, Jumlah Utang = sisa pokok KPR', 'Tab Tidak Bergerak: catat propertinya juga'] },
];

const FORM_CONFIG = {
    pekerjaan: { tabel:'penghasilan_pekerjaan', tabPane:'pekerjaan',
        fields:[
            {id:'pkr_nama', col:'nama_pemberi', type:'text', label:'Nama Pemberi Kerja', required:true,
                hint:'Nama perusahaan/instansi tempat kamu bekerja, sesuai bukti potong 1721-A1 dari kantor.'},
            {id:'pkr_npwp', col:'npwp_pemberi', type:'text', label:'NPWP Pemberi Kerja',
                hint:'NPWP perusahaan pemberi kerja, tercantum di bukti potong 1721-A1.'},
            {id:'pkr_bruto', col:'penghasilan_bruto', type:'money', label:'Penghasilan Bruto', required:true,
                hint:'Total penghasilan setahun SEBELUM dipotong apa pun (gaji pokok + tunjangan + bonus). Lihat kolom "Penghasilan Bruto" di 1721-A1.'},
            {id:'pkr_pph', col:'pph_dipotong', type:'money', label:'PPh Dipotong',
                hint:'Pajak penghasilan yang sudah dipotong otomatis oleh kantor dari gaji kamu setahun, sudah tercantum di 1721-A1 (ini jadi kredit pajak, mengurangi pajak yang masih harus dibayar).'},
            {id:'pkr_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas, misal jabatan atau periode kerja - opsional.'}
        ] },
    utang: { tabel:'utang', tabPane:'utang', kodeSelect:'utang_kode',
        kodeHint:'Kategori utang sesuai daftar resmi DJP, misalnya kartu kredit, KPR, atau utang ke perorangan.',
        fields:[
            {id:'utang_nama', col:'nama_kreditor', type:'text', label:'Nama Kreditor', required:true,
                hint:'Nama pihak yang memberi pinjaman ke kamu (bank, leasing, atau perorangan).'},
            {id:'utang_identitas', col:'identitas_kreditor', type:'text', label:'NIK/NPWP Kreditor',
                hint:'Identitas pemberi pinjaman. Kalau kreditornya bank/lembaga resmi, isi NPWP-nya; kalau perorangan, isi NIK-nya.'},
            {id:'utang_negara', col:'negara_kreditor', type:'text', label:'Negara Kreditor',
                hint:'Negara tempat kreditor berdomisili, biasanya "Indonesia" kecuali utang ke pihak luar negeri.'},
            {id:'utang_th_pinjam', col:'tahun_peminjaman', type:'int', label:'Tahun Peminjaman', fallbackYear:true,
                hint:'Tahun kamu pertama kali mulai berutang/meminjam, bukan tahun pajak yang sedang dilaporkan.'},
            {id:'utang_jumlah', col:'jumlah', type:'money', label:'Jumlah Utang', required:true,
                hint:'Sisa utang yang BELUM lunas per 31 Desember tahun pajak ini (bukan jumlah pinjaman awal).'},
            {id:'utang_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas, misal nomor perjanjian atau tujuan pinjaman - opsional.'}
        ] },
    tanggungan: { tabel:'tanggungan', tabPane:'tanggungan',
        fields:[
            {id:'tgg_nama', col:'nama', type:'text', label:'Nama', required:true,
                hint:'Nama lengkap anggota keluarga yang biaya hidupnya kamu tanggung sepenuhnya.'},
            {id:'tgg_nik', col:'nik', type:'text', label:'NIK', required:true,
                hint:'Nomor Induk Kependudukan (16 digit) anggota keluarga tersebut, sesuai KTP/KK.'},
            {id:'tgg_lahir', col:'tanggal_lahir', type:'text', label:'Tanggal Lahir',
                hint:'Tanggal lahir tanggungan, format tahun-bulan-tanggal.'},
            {id:'tgg_hubungan', col:'hubungan', type:'text', label:'Hubungan',
                hint:'Hubungan keluarga dengan kamu, misalnya "Anak", "Istri", "Suami", atau "Orang Tua".'},
            {id:'tgg_pekerjaan', col:'pekerjaan', type:'text', label:'Pekerjaan',
                hint:'Pekerjaan tanggungan saat ini. Isi "Pelajar/Mahasiswa" atau "Tidak Bekerja" kalau belum bekerja.'},
            {id:'tgg_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas tentang tanggungan ini - opsional.'}
        ] },
    kas: { tabel:'harta_kas', tabPane:'kas', kodeSelect:'kas_kode',
        kodeHint:'Jenis kas/setara kas sesuai daftar resmi DJP: uang tunai, tabungan, deposito, giro, dsb.',
        fields:[
            {id:'kas_bank', col:'nama_bank', type:'text', label:'Nama Bank', required:true,
                hint:'Nama bank atau lembaga tempat kas/tabungan disimpan. Kalau uang tunai di rumah, isi "Tunai".'},
            {id:'kas_rek', col:'no_rekening', type:'text', label:'No Rekening',
                hint:'Nomor rekening bank, kosongkan kalau bukan simpanan di rekening (misal uang tunai).'},
            {id:'kas_lokasi', col:'lokasi', type:'text', label:'Lokasi',
                hint:'Negara/kota tempat rekening atau simpanan berada, biasanya "Indonesia".'},
            {id:'kas_pemilik', col:'pemilik', type:'text', label:'Pemilik',
                hint:'Nama pemilik rekening/harta ini sesuai identitas di bank (biasanya nama kamu sendiri).'},
            {id:'kas_saldo', col:'saldo', type:'money', label:'Saldo', required:true,
                hint:'Saldo/nilai per 31 Desember tahun pajak ini, bukan saldo hari ini.'},
            {id:'kas_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas tentang harta ini - opsional.'}
        ] },
    piutang: { tabel:'harta_piutang', tabPane:'piutang', kodeSelect:'piutang_kode',
        kodeHint:'Jenis piutang: uang yang orang lain masih berutang ke kamu.',
        fields:[
            {id:'piutang_penerima', col:'nama_penerima', type:'text', label:'Nama Penerima', required:true,
                hint:'Nama orang/pihak yang meminjam uang dari kamu (yang masih punya utang ke kamu).'},
            {id:'piutang_lokasi', col:'lokasi_penerima', type:'text', label:'Lokasi',
                hint:'Domisili/alamat pihak yang berutang ke kamu.'},
            {id:'piutang_identitas', col:'identitas_penerima', type:'text', label:'Identitas',
                hint:'NIK atau NPWP pihak yang berutang ke kamu, kalau diketahui.'},
            {id:'piutang_mulai', col:'tahun_mulai', type:'int', label:'Tahun Mulai', fallbackYear:true,
                hint:'Tahun kamu mulai meminjamkan uang tersebut.'},
            {id:'piutang_nilai', col:'nilai_piutang', type:'money', label:'Nilai Piutang', required:true,
                hint:'Jumlah awal yang kamu pinjamkan/piutangkan.'},
            {id:'piutang_saldo', col:'saldo_piutang', type:'money', label:'Saldo Piutang',
                hint:'Sisa piutang yang BELUM dibayar kembali ke kamu per 31 Desember tahun pajak ini.'},
            {id:'piutang_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas, misal alasan/perjanjian peminjaman - opsional.'}
        ] },
    investasi: { tabel:'harta_investasi', tabPane:'investasi', kodeSelect:'inv_kode',
        kodeHint:'Jenis investasi/sekuritas: saham, obligasi, reksa dana, deposito investasi, kripto, dsb.',
        fields:[
            {id:'inv_negara', col:'negara', type:'text', label:'Negara',
                hint:'Negara tempat investasi ini terdaftar/dikelola, biasanya "Indonesia".'},
            {id:'inv_institusi', col:'nama_institusi', type:'text', label:'Institusi', required:true,
                hint:'Nama sekuritas/bank/platform tempat kamu berinvestasi, misal nama broker saham atau aplikasi reksa dana.'},
            {id:'inv_npwp', col:'npwp_institusi', type:'text', label:'NPWP Institusi',
                hint:'NPWP dari institusi/perusahaan investasi tersebut, kalau diketahui.'},
            {id:'inv_akun', col:'no_akun', type:'text', label:'No Akun',
                hint:'Nomor akun/rekening efek/rekening investasi kamu di institusi tersebut.'},
            {id:'inv_th_perol', col:'tahun_perolehan', type:'int', label:'Tahun Perolehan', fallbackYear:true,
                hint:'Tahun pertama kali kamu membeli/memperoleh investasi ini.'},
            {id:'inv_harga', col:'harga_perolehan', type:'money', label:'Harga Perolehan', required:true,
                hint:'Harga saat kamu pertama kali membeli investasi ini (harga beli, bukan harga sekarang).'},
            {id:'inv_nilai', col:'nilai_saat_ini', type:'money', label:'Nilai Saat Ini',
                hint:'Perkiraan nilai wajar/nilai pasar investasi ini per 31 Desember tahun pajak.'},
            {id:'inv_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas tentang investasi ini - opsional.'}
        ] },
    bergerak: { tabel:'harta_bergerak', tabPane:'bergerak', kodeSelect:'bg_kode',
        kodeHint:'Jenis harta bergerak: kendaraan, mesin, dan barang bergerak lain yang bisa dipindahkan.',
        fields:[
            {id:'bg_merk', col:'merk', type:'text', label:'Merk/Model', required:true,
                hint:'Merk dan model kendaraan/barang, misal "Toyota Avanza" atau "Honda Beat".'},
            {id:'bg_nopol', col:'no_polisi', type:'text', label:'No Polisi',
                hint:'Nomor plat kendaraan, kosongkan kalau bukan kendaraan bermotor.'},
            {id:'bg_kepemilikan', col:'kepemilikan', type:'text', label:'Kepemilikan',
                hint:'Status kepemilikan, misal "Milik Sendiri" atau "Atas Nama Orang Lain".'},
            {id:'bg_th_perol', col:'tahun_perolehan', type:'int', label:'Tahun Perolehan', fallbackYear:true,
                hint:'Tahun kamu membeli/memperoleh barang ini.'},
            {id:'bg_harga', col:'harga_perolehan', type:'money', label:'Harga Perolehan', required:true,
                hint:'Harga beli barang ini saat pertama kali diperoleh.'},
            {id:'bg_nilai', col:'nilai_saat_ini', type:'money', label:'Nilai Saat Ini',
                hint:'Perkiraan nilai jual/nilai pasar barang ini sekarang (biasanya lebih rendah dari harga beli karena penyusutan).'},
            {id:'bg_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas tentang harta ini - opsional.'}
        ] },
    tidakbergerak: { tabel:'harta_tidak_bergerak', tabPane:'tidakbergerak', kodeSelect:'tbg_kode',
        kodeHint:'Jenis harta tidak bergerak: tanah, rumah, apartemen, ruko, dsb.',
        fields:[
            {id:'tbg_lokasi', col:'lokasi', type:'text', label:'Lokasi/Alamat', required:true,
                hint:'Alamat lengkap properti (jalan, kota/kabupaten, provinsi).'},
            {id:'tbg_luas_tanah', col:'luas_tanah', type:'int', label:'Luas Tanah',
                hint:'Luas tanah dalam meter persegi (m²), sesuai sertifikat.'},
            {id:'tbg_luas_bangun', col:'luas_bangunan', type:'int', label:'Luas Bangunan',
                hint:'Luas bangunan dalam meter persegi (m²), kosongkan kalau tanah kosong.'},
            {id:'tbg_th_perol', col:'tahun_perolehan', type:'int', label:'Tahun Perolehan', fallbackYear:true,
                hint:'Tahun kamu membeli/memperoleh properti ini.'},
            {id:'tbg_harga', col:'harga_perolehan', type:'money', label:'Harga Perolehan', required:true,
                hint:'Harga beli properti ini saat pertama kali diperoleh (harga di akta jual-beli).'},
            {id:'tbg_nilai', col:'nilai_saat_ini', type:'money', label:'Nilai Saat Ini',
                hint:'Perkiraan nilai jual pasar properti ini sekarang (bisa lebih tinggi dari harga beli karena kenaikan harga tanah).'},
            {id:'tbg_sertifikat', col:'sertifikat', type:'text', label:'Sertifikat',
                hint:'Jenis sertifikat kepemilikan, misal SHM (Hak Milik), HGB (Hak Guna Bangunan), atau Girik.'},
            {id:'tbg_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas tentang properti ini - opsional.'}
        ] },
    lainnya: { tabel:'harta_lainnya', tabPane:'lainnya', kodeSelect:'lain_kode',
        kodeHint:'Jenis harta lainnya: emas, perhiasan, barang seni, hak paten/merek, elektronik, dsb.',
        fields:[
            {id:'lain_th_perol', col:'tahun_perolehan', type:'int', label:'Tahun Perolehan', fallbackYear:true,
                hint:'Tahun kamu membeli/memperoleh harta ini.'},
            {id:'lain_bukti', col:'bukti_kepemilikan', type:'text', label:'Bukti Kepemilikan/No Akun',
                hint:'Nomor bukti kepemilikan/nomor akun/sertifikat harta ini, kalau ada. Sesuai kolom Coretax "Bukti Kepemilikan/Nomor Akun".'},
            {id:'lain_harga', col:'harga_perolehan', type:'money', label:'Harga Perolehan', required:true,
                hint:'Harga beli harta ini saat pertama kali diperoleh.'},
            {id:'lain_nilai', col:'nilai_saat_ini', type:'money', label:'Nilai Saat Ini',
                hint:'Perkiraan nilai jual/nilai pasar harta ini sekarang.'},
            {id:'lain_keterangan', col:'keterangan', type:'text', label:'Informasi Tambahan',
                hint:'Deskripsi singkat harta ini, misal jenis/berat emas, atau nama merek/paten.'}
        ] },
    final: { tabel:'penghasilan_final', tabPane:'penghasilanlain', kodeSelect:'final_kode',
        kodeHint:'Penghasilan yang pajaknya sudah "final"/selesai saat diterima, jadi tidak dihitung ulang bersama gaji.',
        fields:[
            {id:'final_bruto', col:'jumlah_bruto', type:'money', label:'Jumlah Bruto', required:true,
                hint:'Jumlah penghasilan ini SEBELUM dipotong pajak final, misal total bunga tabungan setahun.'},
            {id:'final_pph', col:'pph_final', type:'money', label:'PPh Final Dibayar',
                hint:'Pajak yang sudah otomatis dipotong/dibayar atas penghasilan ini (misal bank sudah memotong pajak bunga tabungan).'},
            {id:'final_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas, misal sumber/pihak pemotong pajak - opsional.'}
        ] },
    bukanobjek: { tabel:'penghasilan_bukan_objek', tabPane:'penghasilanlain', kodeSelect:'bukanobjek_kode',
        kodeHint:'Penghasilan yang menurut aturan pajak memang TIDAK dikenakan pajak sama sekali.',
        fields:[
            {id:'bukanobjek_jumlah', col:'jumlah', type:'money', label:'Jumlah', required:true,
                hint:'Jumlah penghasilan/uang yang kamu terima, misal nilai warisan atau hibah yang diterima.'},
            {id:'bukanobjek_info', col:'informasi_tambahan', type:'text', label:'Informasi Tambahan',
                hint:'Catatan bebas, misal dari siapa/hubungan dengan pemberi - opsional.'}
        ] },
    zakat: { tabel:'zakat', tabPane:'penghasilanlain',
        fields:[
            {id:'zkt_deskripsi', col:'deskripsi', type:'text', label:'Deskripsi', required:true,
                hint:'Jenis zakat/sumbangan, misal "Zakat Penghasilan" atau "Sumbangan Keagamaan Wajib".'},
            {id:'zkt_lembaga', col:'lembaga', type:'text', label:'Lembaga Penerima',
                hint:'Nama lembaga amil zakat/keagamaan resmi yang menerima, misal BAZNAS. Harus lembaga yang diakui pemerintah supaya bisa jadi pengurang pajak.'},
            {id:'zkt_jumlah', col:'jumlah', type:'money', label:'Jumlah', required:true,
                hint:'Jumlah zakat/sumbangan yang dibayarkan. Ini akan mengurangi penghasilan neto sebelum dihitung PTKP dan PPh.'}
        ] },
    catatan: { tabel:'catatan_penghasilan', tabPane:'catatan',
        fields:[
            {id:'ctt_tanggal', col:'tanggal', type:'text', label:'Tanggal',
                hint:'Tanggal kamu menerima penghasilan ini, supaya gampang diingat nanti.'},
            {id:'ctt_deskripsi', col:'deskripsi', type:'text', label:'Deskripsi', required:true,
                hint:'Deskripsi singkat sumber penghasilannya, misal "Honor desain logo untuk klien X".'},
            {id:'ctt_jumlah', col:'perkiraan_jumlah', type:'money', label:'Perkiraan Jumlah', required:true,
                hint:'Perkiraan jumlah yang diterima. Boleh belum pasti/dibulatkan, nanti dikoreksi saat dimasukkan resmi.'},
            {id:'ctt_kategori', col:'kategori', type:'text', label:'Kategori',
                hint:'Perkiraan kategori pajaknya nanti: Pekerjaan (kena PPh progresif), Final (sudah dipotong di sumber), atau Bukan Objek (tidak kena pajak).'},
            {id:'ctt_keterangan', col:'keterangan', type:'text', label:'Keterangan',
                hint:'Catatan tambahan, misal nama klien atau bukti transfer.'},
            {id:'ctt_status', col:'status', type:'text', default:'belum'}
        ] }
};

let EDIT_STATE = {};
let LAST_DATA = {};
let LAST_IDENTITAS = {};

const IDENTITAS_HINTS = {
    identitas_nik: 'Nomor Induk Kependudukan, 16 digit sesuai KTP kamu.',
    identitas_npwp: 'Nomor Pokok Wajib Pajak. Sejak pemadanan NIK-NPWP, NIK kamu otomatis berfungsi sebagai NPWP - boleh dikosongkan kalau belum punya NPWP format lama.',
    identitas_nama: 'Nama lengkap sesuai KTP/NPWP.',
    identitas_telepon: 'Nomor telepon aktif untuk keperluan komunikasi terkait pajak.',
    identitas_email: 'Email aktif, biasanya sama dengan email yang terdaftar di akun DJP Online/Coretax.',
    identitas_status: 'Status pernikahan per akhir tahun pajak: TK (Tidak Kawin) atau K (Kawin).',
    identitas_ptkp: 'Penghasilan Tidak Kena Pajak - batas penghasilan yang tidak dikenakan pajak. Angka di belakang garis miring adalah jumlah tanggungan (anak/keluarga yang biayanya kamu tanggung penuh, maksimal dihitung 3 orang).'
};

function tokenizeQuery(s) {
    return (s || '').toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length > 1);
}

function cariSaran() {
    const q = document.getElementById('tanya_input').value.toLowerCase().trim();
    const hasil = document.getElementById('tanyaHasil');
    if (!q) { hasil.innerHTML = ''; return; }
    const qTokens = tokenizeQuery(q);
    const scored = KNOWLEDGE_BASE.map(entry => {
        let score = 0;
        entry.keywords.forEach(kw => {
            const kwLower = kw.toLowerCase();
            if (q.includes(kwLower) || kwLower.includes(q)) score += kwLower.length * 2;
            tokenizeQuery(kwLower).forEach(t => { if (qTokens.includes(t)) score += 5; });
        });
        return { entry, score };
    }).filter(x => x.score > 0).sort((a, b) => b.score - a.score);

    if (scored.length === 0) {
        hasil.innerHTML = `<div class="card"><div class="card-body text-muted">
            Tidak ada saran spesifik untuk "<b>${q}</b>". Coba kata kunci lain (nama aplikasi/bank, jenis transaksi),
            atau tanyakan ke AR pajak/konsultan pajak untuk kasus yang tidak umum.
        </div></div>`;
        return;
    }
    hasil.innerHTML = scored.slice(0, 5).map(x => x.entry).map(h => `
        <div class="card">
            <div class="card-header"><i class="bi bi-lightbulb"></i>${h.judul}</div>
            <div class="card-body">
                <span class="badge bg-primary mb-2">${h.masuk_tab}</span>
                <p class="mb-2">${h.penjelasan}</p>
                ${h.pajak_tambahan ? `<p class="mb-2"><b>Pajak tambahan:</b> ${h.pajak_tambahan}</p>` : ''}
                ${h.cara_isi ? `<div class="mb-2"><b>Cara isi field-nya:</b><ul class="mb-0">${h.cara_isi.map(c => `<li>${c}</li>`).join('')}</ul></div>` : ''}
                ${h.catatan ? `<p class="mb-0 text-muted small"><i class="bi bi-info-circle"></i> ${h.catatan}</p>` : ''}
            </div>
        </div>
    `).join('');
}

function attachFieldHints() {
    function addHint(id, text) {
        if (!text) return;
        const el = document.getElementById(id);
        if (!el) return;
        const label = el.previousElementSibling;
        if (!label || label.querySelector('.field-hint-icon')) return;
        const icon = document.createElement('i');
        icon.className = 'bi bi-info-circle field-hint-icon';
        icon.setAttribute('data-bs-toggle', 'tooltip');
        icon.setAttribute('data-bs-placement', 'top');
        icon.setAttribute('title', text);
        label.appendChild(icon);
    }
    Object.values(FORM_CONFIG).forEach(cfg => {
        cfg.fields.forEach(f => addHint(f.id, f.hint));
        if (cfg.kodeSelect) addHint(cfg.kodeSelect, cfg.kodeHint);
    });
    Object.entries(IDENTITAS_HINTS).forEach(([id, text]) => addHint(id, text));
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
}

function formatMoneyLive(el) {
    const raw = el.value.replace(/\\D/g,'');
    el.value = raw ? Number(raw).toLocaleString('id-ID') : '';
}
function parseMoney(val) {
    return parseInt(String(val).replace(/\\D/g,'')) || 0;
}
function currentTahunPajak() {
    return parseInt(document.getElementById('tahunPajak').value) || new Date().getFullYear();
}

function populateDropdowns() {
    function fill(id, list) {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = '';
        list.forEach(item => {
            const opt = document.createElement('option');
            opt.value = item.kode;
            opt.textContent = item.kode + ' - ' + item.desc;
            opt.dataset.desc = item.desc;
            el.appendChild(opt);
        });
    }
    fill('utang_kode', KODE_UTANG);
    fill('kas_kode', KODE_KAS);
    fill('piutang_kode', KODE_PIUTANG);
    fill('inv_kode', KODE_INVESTASI);
    fill('bg_kode', KODE_BERGERAK);
    fill('tbg_kode', KODE_TIDAK_BERGERAK);
    fill('lain_kode', KODE_LAINNYA);
    fill('final_kode', KODE_FINAL);
    fill('bukanobjek_kode', KODE_BUKAN_OBJEK);

    const ptkpEl = document.getElementById('identitas_ptkp');
    ptkpEl.innerHTML = '';
    PTKP_OPTIONS.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p.kode; opt.textContent = p.label;
        ptkpEl.appendChild(opt);
    });
}

function initTahunSelect() {
    const el = document.getElementById('tahunPajak');
    const now = new Date().getFullYear();
    el.innerHTML = '';
    for (let y = now; y >= now - 10; y--) {
        const opt = document.createElement('option');
        opt.value = y; opt.textContent = y;
        el.appendChild(opt);
    }
    el.value = now;
}

function sum(arr, key) {
    return arr.reduce((a,b) => a + (b[key]||0), 0);
}

const YEAR_FIELDS = new Set(['tahun_peminjaman', 'tahun_mulai', 'tahun_perolehan']);

function renderTabel(id, data, fields, cfg) {
    const tbody = document.getElementById(id);
    if (!tbody) return;
    if (!data || data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="20" class="text-center text-muted">Tidak ada data</td></tr>`;
        return;
    }
    let html = '';
    data.forEach(item => {
        let row = '';
        fields.forEach(f => {
            let val = item[f] !== undefined ? item[f] : '-';
            if (typeof val === 'number' && !YEAR_FIELDS.has(f)) val = val.toLocaleString('id-ID');
            row += `<td>${val}</td>`;
        });
        row += `<td class="text-nowrap">
            <button class="btn btn-sm btn-outline-primary me-1" onclick="editRow(FORM_CONFIG.${cfg}, ${item.id})"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-sm btn-outline-danger" onclick="hapus('${FORM_CONFIG[cfg].tabel}', ${item.id})"><i class="bi bi-trash"></i></button>
        </td>`;
        html += `<tr>${row}</tr>`;
    });
    tbody.innerHTML = html;
}

function renderCatatanTabel(data) {
    const tbody = document.getElementById('tabelCatatan');
    if (!data || data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">Belum ada catatan</td></tr>`;
        return;
    }
    let html = '';
    data.forEach(item => {
        const badge = item.status === 'sudah'
            ? `<button class="btn btn-sm btn-success" onclick="toggleCatatanStatus(${item.id})">✅ Sudah</button>`
            : `<button class="btn btn-sm btn-outline-warning" onclick="toggleCatatanStatus(${item.id})">⏳ Belum</button>`;
        html += `<tr>
            <td>${item.tanggal || '-'}</td>
            <td>${item.deskripsi}</td>
            <td class="text-end">${(item.perkiraan_jumlah||0).toLocaleString('id-ID')}</td>
            <td>${item.kategori || '-'}</td>
            <td>${badge}</td>
            <td>${item.keterangan || '-'}</td>
            <td class="text-nowrap">
                <button class="btn btn-sm btn-outline-primary me-1" onclick="editRow(FORM_CONFIG.catatan, ${item.id})"><i class="bi bi-pencil"></i></button>
                <button class="btn btn-sm btn-outline-danger" onclick="hapus('catatan_penghasilan', ${item.id})"><i class="bi bi-trash"></i></button>
            </td>
        </tr>`;
    });
    tbody.innerHTML = html;
}

function renderChecklist(d) {
    const idnt = LAST_IDENTITAS || {};
    const belum = (d.catatan || []).filter(c => c.status === 'belum').length;
    const items = [
        { label: 'Identitas (NIK, Nama, Status PTKP) terisi', ok: !!(idnt.nik && idnt.nama && idnt.ptkp_status) },
        { label: 'Ada sumber penghasilan tercatat (Pekerjaan/Final)', ok: (d.pekerjaan.length > 0 || d.final.length > 0) },
        { label: 'Ada data harta tercatat', ok: (d.kas.length + d.piutang.length + d.investasi.length + d.bergerak.length + d.tidakbergerak.length + d.lainnya.length) > 0 },
        { label: belum > 0 ? `Semua catatan penghasilan sudah diproses (${belum} masih menunggu)` : 'Semua catatan penghasilan sudah diproses', ok: belum === 0 }
    ];
    let html = '';
    items.forEach(it => {
        html += `<li class="list-group-item d-flex align-items-center gap-2">
            <i class="bi ${it.ok ? 'bi-check-circle-fill text-success' : 'bi-exclamation-circle-fill text-warning'}"></i>
            <span>${it.label}</span>
        </li>`;
    });
    document.getElementById('checklistBody').innerHTML = html;
}

async function renderReviewTab(d, tahun) {
    const r = d.rekap;
    renderChecklist(d);
    document.getElementById('reviewPphTerutang').innerHTML = 'Rp ' + (r.pph_terutang||0).toLocaleString('id-ID');
    const badge = document.getElementById('reviewStatusBadge');
    if (r.status_bayar > 0) { badge.innerHTML = '🔴 Kurang Bayar Rp '+r.status_bayar.toLocaleString('id-ID'); badge.className='badge bg-danger badge-status'; }
    else if (r.status_bayar < 0) { badge.innerHTML = '🟢 Lebih Bayar Rp '+Math.abs(r.status_bayar).toLocaleString('id-ID'); badge.className='badge bg-success badge-status'; }
    else { badge.innerHTML = '⚪ Nihil'; badge.className='badge bg-secondary badge-status'; }

    const belum = (d.catatan || []).filter(c => c.status === 'belum');
    const tbodyBelum = document.getElementById('tabelCatatanBelumReview');
    if (belum.length === 0) {
        tbodyBelum.innerHTML = `<tr><td colspan="4" class="text-center text-muted">Semua catatan sudah diproses</td></tr>`;
    } else {
        tbodyBelum.innerHTML = belum.map(c => `<tr>
            <td>${c.tanggal || '-'}</td><td>${c.deskripsi}</td>
            <td class="text-end">${(c.perkiraan_jumlah||0).toLocaleString('id-ID')}</td>
            <td>${c.kategori || '-'}</td>
        </tr>`).join('');
    }

    document.getElementById('kekayaanIni').innerHTML = 'Rp ' + (r.kekayaan||0).toLocaleString('id-ID');
    try {
        const resPrev = await fetch('/api/data?tahun=' + (tahun - 1));
        const dPrev = await resPrev.json();
        const kekayaanLalu = dPrev.rekap.kekayaan || 0;
        const selisih = (r.kekayaan||0) - kekayaanLalu;
        document.getElementById('kekayaanLalu').innerHTML = 'Rp ' + kekayaanLalu.toLocaleString('id-ID');
        document.getElementById('selisihKekayaan').innerHTML = (selisih >= 0 ? '+' : '-') + 'Rp ' + Math.abs(selisih).toLocaleString('id-ID');
    } catch(e) { /* abaikan, bukan bagian kritis */ }
}

async function ambilData() {
    const tahun = document.getElementById('tahunPajak').value;
    try {
        const res = await fetch('/api/data?tahun='+tahun);
        const d = await res.json();
        LAST_DATA = d;
        const r = d.rekap;

        document.getElementById('totalGross').innerHTML = 'Rp ' + (r.total_bruto||0).toLocaleString('id-ID');
        document.getElementById('totalZakat').innerHTML = 'Rp ' + (r.total_zakat||0).toLocaleString('id-ID');
        document.getElementById('totalNeto').innerHTML = 'Rp ' + (r.neto_setelah_zakat||0).toLocaleString('id-ID');
        document.getElementById('pphTerutang').innerHTML = 'Rp ' + (r.pph_terutang||0).toLocaleString('id-ID');
        document.getElementById('totalPphDipotong').innerHTML = 'Rp ' + (r.total_pph_dipotong||0).toLocaleString('id-ID');
        document.getElementById('totalFinalBruto').innerHTML = 'Rp ' + (r.total_final_bruto||0).toLocaleString('id-ID');
        document.getElementById('totalFinalPph').innerHTML = 'Rp ' + (r.total_final_pph||0).toLocaleString('id-ID');
        document.getElementById('totalBukanObjek').innerHTML = 'Rp ' + (r.total_bukan_objek||0).toLocaleString('id-ID');
        document.getElementById('totalHarta').innerHTML = 'Rp ' + (r.total_nilai||0).toLocaleString('id-ID');
        document.getElementById('totalUtang').innerHTML = 'Rp ' + (r.total_utang||0).toLocaleString('id-ID');
        document.getElementById('kekayaanBersih').innerHTML = 'Rp ' + (r.kekayaan||0).toLocaleString('id-ID');
        document.getElementById('ptkpDisplay').innerHTML = 'Rp ' + (r.ptkp||0).toLocaleString('id-ID') + ' (' + (r.ptkp_status||'') + ')';

        const badge = document.getElementById('statusBadge');
        if (r.status_bayar > 0) { badge.innerHTML = '🔴 Kurang Bayar Rp '+r.status_bayar.toLocaleString('id-ID'); badge.className='badge bg-danger badge-status'; }
        else if (r.status_bayar < 0) { badge.innerHTML = '🟢 Lebih Bayar Rp '+Math.abs(r.status_bayar).toLocaleString('id-ID'); badge.className='badge bg-success badge-status'; }
        else { badge.innerHTML = '⚪ Nihil'; badge.className='badge bg-secondary badge-status'; }

        const ikhtisar = [
            {label:'Kas', hp: sum(d.kas,'saldo'), nilai: sum(d.kas,'saldo')},
            {label:'Piutang', hp: sum(d.piutang,'nilai_piutang'), nilai: sum(d.piutang,'saldo_piutang')},
            {label:'Investasi', hp: sum(d.investasi,'harga_perolehan'), nilai: sum(d.investasi,'nilai_saat_ini')},
            {label:'Bergerak', hp: sum(d.bergerak,'harga_perolehan'), nilai: sum(d.bergerak,'nilai_saat_ini')},
            {label:'Tidak Bergerak', hp: sum(d.tidakbergerak,'harga_perolehan'), nilai: sum(d.tidakbergerak,'nilai_saat_ini')},
            {label:'Lainnya', hp: sum(d.lainnya,'harga_perolehan'), nilai: sum(d.lainnya,'nilai_saat_ini')}
        ];
        let htmlI = '';
        ikhtisar.forEach(item => {
            htmlI += `<tr><td>${item.label}</td><td class="text-end">${item.hp.toLocaleString('id-ID')}</td><td class="text-end">${item.nilai.toLocaleString('id-ID')}</td></tr>`;
        });
        htmlI += `<tr class="fw-bold"><td>TOTAL</td><td class="text-end">${r.total_hp.toLocaleString('id-ID')}</td><td class="text-end">${r.total_nilai.toLocaleString('id-ID')}</td></tr>`;
        document.getElementById('ikhtisarBody').innerHTML = htmlI;

        renderTabel('tabelPekerjaan', d.pekerjaan, ['nama_pemberi','npwp_pemberi','penghasilan_bruto','biaya_jabatan','penghasilan_neto','pph_dipotong','informasi_tambahan'], 'pekerjaan');
        renderTabel('tabelUtang', d.utang, ['kode','deskripsi','nama_kreditor','identitas_kreditor','negara_kreditor','tahun_peminjaman','jumlah','informasi_tambahan'], 'utang');
        renderTabel('tabelTanggungan', d.tanggungan, ['nama','nik','tanggal_lahir','hubungan','pekerjaan','informasi_tambahan'], 'tanggungan');
        renderTabel('tabelKas', d.kas, ['kode','deskripsi','nama_bank','no_rekening','lokasi','pemilik','saldo','informasi_tambahan'], 'kas');
        renderTabel('tabelPiutang', d.piutang, ['kode','deskripsi','nama_penerima','lokasi_penerima','identitas_penerima','tahun_mulai','nilai_piutang','saldo_piutang','informasi_tambahan'], 'piutang');
        renderTabel('tabelInvestasi', d.investasi, ['kode','deskripsi','negara','nama_institusi','npwp_institusi','no_akun','tahun_perolehan','harga_perolehan','nilai_saat_ini','informasi_tambahan'], 'investasi');
        renderTabel('tabelBergerak', d.bergerak, ['kode','deskripsi','merk','no_polisi','kepemilikan','tahun_perolehan','harga_perolehan','nilai_saat_ini','informasi_tambahan'], 'bergerak');
        renderTabel('tabelTidakBergerak', d.tidakbergerak, ['kode','deskripsi','lokasi','luas_tanah','luas_bangunan','tahun_perolehan','harga_perolehan','nilai_saat_ini','sertifikat','informasi_tambahan'], 'tidakbergerak');
        renderTabel('tabelLainnya', d.lainnya, ['kode','deskripsi','tahun_perolehan','bukti_kepemilikan','harga_perolehan','nilai_saat_ini','keterangan'], 'lainnya');
        renderTabel('tabelFinal', d.final, ['kode','deskripsi','jumlah_bruto','pph_final','informasi_tambahan'], 'final');
        renderTabel('tabelBukanObjek', d.bukanobjek, ['kode','deskripsi','jumlah','informasi_tambahan'], 'bukanobjek');
        renderTabel('tabelZakat', d.zakat, ['deskripsi','lembaga','jumlah'], 'zakat');
        renderCatatanTabel(d.catatan);
        renderReviewTab(d, parseInt(tahun));

        const sel = document.getElementById('tahunPajak');
        const cur = parseInt(sel.value);
        sel.innerHTML = '';
        if (r.list_tahun && r.list_tahun.length > 0) {
            r.list_tahun.forEach(y => {
                const opt = document.createElement('option');
                opt.value = y; opt.textContent = y;
                sel.appendChild(opt);
            });
            if (r.list_tahun.includes(cur)) sel.value = cur;
            else sel.value = r.list_tahun[0];
        }
    } catch(e) { console.error(e); alert('Error: '+e.message); }
}

function fieldValue(f) {
    const el = document.getElementById(f.id);
    if (!el) return f.type === 'text' ? '' : 0;
    if (f.type === 'money') return parseMoney(el.value);
    if (f.type === 'int') return parseInt(el.value) || (f.fallbackYear ? currentTahunPajak() : 0);
    return el.value.trim();
}

function collectFormData(cfg) {
    const data = {};
    cfg.fields.forEach(f => { data[f.col] = fieldValue(f); });
    if (cfg.kodeSelect) {
        const sel = document.getElementById(cfg.kodeSelect);
        data.kode = sel.value;
        data.deskripsi = sel.options[sel.selectedIndex].dataset.desc;
    }
    data.tahun = currentTahunPajak();
    return data;
}

function validateForm(cfg, data) {
    for (const f of cfg.fields) {
        if (f.required && !data[f.col]) {
            alert('Mohon isi: ' + f.label);
            return false;
        }
    }
    return true;
}

function resetFormFields(cfg) {
    cfg.fields.forEach(f => {
        const el = document.getElementById(f.id);
        if (el) el.value = f.default !== undefined ? f.default : '';
    });
}

function fillFormFields(cfg, item) {
    cfg.fields.forEach(f => {
        const el = document.getElementById(f.id);
        if (!el) return;
        const v = item[f.col];
        if (f.type === 'money') el.value = v ? Number(v).toLocaleString('id-ID') : '';
        else el.value = (v !== undefined && v !== null) ? v : '';
    });
    if (cfg.kodeSelect && item.kode) document.getElementById(cfg.kodeSelect).value = item.kode;
}

function setEditMode(cfg, id) {
    EDIT_STATE[cfg.tabel] = id;
    const btn = document.getElementById('btn_' + cfg.tabel);
    const cancelBtn = document.getElementById('cancel_' + cfg.tabel);
    if (id) {
        if (btn) { btn.textContent = 'Update'; btn.classList.remove('btn-primary'); btn.classList.add('btn-warning'); }
        if (cancelBtn) cancelBtn.classList.add('show');
    } else {
        if (btn) { btn.textContent = 'Simpan'; btn.classList.remove('btn-warning'); btn.classList.add('btn-primary'); }
        if (cancelBtn) cancelBtn.classList.remove('show');
    }
}

async function apiSimpan(tabel, data) {
    const id = EDIT_STATE[tabel];
    const url = id ? `/api/item/${tabel}/${id}` : `/api/item/${tabel}`;
    const method = id ? 'PUT' : 'POST';
    const res = await fetch(url, { method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(data) });
    if (!res.ok) { alert('Gagal menyimpan data'); return; }
    EDIT_STATE[tabel] = null;
    await ambilData();
}

window.submitForm = async function(cfg) {
    const data = collectFormData(cfg);
    if (!validateForm(cfg, data)) return;
    await apiSimpan(cfg.tabel, data);
    resetFormFields(cfg);
    setEditMode(cfg, null);
};

window.editRow = function(cfg, id) {
    const dataKey = Object.keys(FORM_CONFIG).find(k => FORM_CONFIG[k] === cfg);
    const list = LAST_DATA[dataKey] || [];
    const item = list.find(x => x.id === id);
    if (!item) return;
    fillFormFields(cfg, item);
    setEditMode(cfg, id);
    const tabBtn = document.getElementById('tab-btn-' + cfg.tabPane);
    if (tabBtn) new bootstrap.Tab(tabBtn).show();
    const formEl = document.getElementById('form_' + cfg.tabel);
    if (formEl) formEl.scrollIntoView({behavior:'smooth', block:'start'});
};

window.cancelEdit = function(cfg) {
    resetFormFields(cfg);
    setEditMode(cfg, null);
};

window.hapus = async function(tabel, id) {
    if (!confirm('Hapus data ini?')) return;
    await fetch(`/api/item/${tabel}/${id}`, {method:'DELETE'});
    ambilData();
};

window.simpanIdentitas = async function() {
    const data = {
        nik: document.getElementById('identitas_nik').value,
        npwp: document.getElementById('identitas_npwp').value,
        nama: document.getElementById('identitas_nama').value,
        telepon: document.getElementById('identitas_telepon').value,
        email: document.getElementById('identitas_email').value,
        status_kawin: document.getElementById('identitas_status').value,
        ptkp_status: document.getElementById('identitas_ptkp').value
    };
    await fetch('/api/identitas', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) });
    LAST_IDENTITAS = {...data, id: 1};
    alert('Identitas tersimpan');
    ambilData();
};

window.ambilIdentitas = async function() {
    const res = await fetch('/api/identitas');
    const data = await res.json();
    LAST_IDENTITAS = data;
    if (data.id) {
        document.getElementById('identitas_nik').value = data.nik||'';
        document.getElementById('identitas_npwp').value = data.npwp||'';
        document.getElementById('identitas_nama').value = data.nama||'';
        document.getElementById('identitas_telepon').value = data.telepon||'';
        document.getElementById('identitas_email').value = data.email||'';
        document.getElementById('identitas_status').value = data.status_kawin||'TK';
        document.getElementById('identitas_ptkp').value = data.ptkp_status||'TK/0';
    }
};

window.toggleCatatanStatus = async function(id) {
    const item = (LAST_DATA.catatan || []).find(x => x.id === id);
    if (!item) return;
    const newStatus = item.status === 'sudah' ? 'belum' : 'sudah';
    const payload = {
        tanggal: item.tanggal, deskripsi: item.deskripsi, perkiraan_jumlah: item.perkiraan_jumlah,
        kategori: item.kategori, status: newStatus, keterangan: item.keterangan, tahun: item.tahun
    };
    await fetch(`/api/item/catatan_penghasilan/${id}`, {
        method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    ambilData();
};

window.exportPdf = function() {
    window.location.href = '/api/export_pdf?tahun=' + currentTahunPajak();
};

window.salinDariTahunLalu = async function() {
    const ke = currentTahunPajak();
    const dari = ke - 1;
    if (!confirm(`Salin data Harta, Utang, dan Tanggungan dari tahun ${dari} ke tahun ${ke}?\\n\\nData yang sudah ada di tahun ${ke} tidak akan dihapus/ditimpa, hanya ditambahkan yang baru dari tahun ${dari}.`)) return;
    const res = await fetch('/api/salin_tahun', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({dari_tahun: dari, ke_tahun: ke})
    });
    const d = await res.json();
    if (d.status === 'ok') {
        const total = Object.values(d.hasil).reduce((a,b) => a+b, 0);
        alert(total > 0 ? `Berhasil menyalin ${total} item dari tahun ${dari}.` : `Tidak ada data di tahun ${dari} untuk disalin.`);
        ambilData();
    } else {
        alert('Gagal menyalin: ' + (d.msg || ''));
    }
};

window.onload = async function() {
    populateDropdowns();
    initTahunSelect();
    attachFieldHints();
    await ambilIdentitas();
    await ambilData();
};
</script>
</body>
</html>
"""

if __name__ == '__main__':
    # host default 127.0.0.1 (localhost saja) - jangan ganti ke 0.0.0.0 tanpa
    # menambah autentikasi, karena tidak ada login di endpoint API manapun.
    app.run(debug=False, port=5000)
