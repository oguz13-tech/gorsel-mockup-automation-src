import sqlite3
import json
import os

# DB yolu: SABLON_V2_MIMARI/ayarlar.db
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "ayarlar.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_schema(conn):
    """Single idempotent schema migration point. Add all ALTER TABLE operations here."""
    c = conn.cursor()
    migrations = [
        ("nominal_aspect", "ALTER TABLE template_profiles ADD COLUMN nominal_aspect TEXT"),
        ("is_active", "ALTER TABLE template_profiles ADD COLUMN is_active INTEGER DEFAULT 1"),
    ]
    for col_name, alter_sql in migrations:
        try:
            c.execute(f"SELECT {col_name} FROM template_profiles LIMIT 1")
        except sqlite3.OperationalError:
            c.execute(alter_sql)


def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Kategoriler Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    label TEXT
                 )''')
    # Sablonlar Tablosu (data sütunu JSON formatında string tutar)
    c.execute('''CREATE TABLE IF NOT EXISTS templates (
                    category_id TEXT,
                    filename TEXT,
                    data TEXT,
                    PRIMARY KEY (category_id, filename)
                 )''')
    # Genel Ayarlar Tablosu
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                 )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS template_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_uid TEXT,
                    category TEXT,
                    source_relative_path TEXT,
                    source_asset_sha256 TEXT,
                    profile_version TEXT,
                    analyzer_version TEXT,
                    product_class TEXT,
                    orientation TEXT,
                    nominal_aspect TEXT,
                    geometry_type TEXT,
                    print_policy TEXT,
                    surface_quad TEXT,
                    outer_quad TEXT,
                    surface_mask_path TEXT,
                    material TEXT,
                    has_frame INTEGER,
                    has_mat INTEGER,
                    has_reflection INTEGER,
                    has_occlusion INTEGER,
                    confidence_total REAL,
                    component_confidences TEXT,
                    review_status TEXT,
                    manually_verified INTEGER,
                    is_active INTEGER DEFAULT 1,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')

    # Run idempotent migrations for existing DBs
    migrate_schema(conn)

    conn.commit()
    conn.close()

def get_all_ayarlar():
    """Tüm veritabanını okuyup, frontend'in beklediği devasa JSON yapısını anında oluşturur."""
    conn = get_db_connection()
    c = conn.cursor()
    
    result = {"kategoriler": {}}
    
    # 1. Genel ayarları çek (bulut_ayarlari vb.)
    c.execute("SELECT key, value FROM settings")
    for row in c.fetchall():
        result[row["key"]] = json.loads(row["value"])
        
    # 2. Kategorileri çek
    c.execute("SELECT id, label FROM categories")
    for row in c.fetchall():
        cat_id = row["id"]
        result["kategoriler"][cat_id] = {
            "etiket": row["label"],
            "sablonlar": {}
        }
        
    # 3. Tüm şablonları çek ve ilgili kategoriye yerleştir
    c.execute("SELECT category_id, filename, data FROM templates")
    for row in c.fetchall():
        cat_id = row["category_id"]
        tmpl = row["filename"]
        data = json.loads(row["data"])
        
        # Eğer kategori henüz result içinde yoksa güvenli bir şekilde oluştur
        if cat_id not in result["kategoriler"]:
            result["kategoriler"][cat_id] = {"sablonlar": {}}
            
        if "sablonlar" not in result["kategoriler"][cat_id]:
            result["kategoriler"][cat_id]["sablonlar"] = {}
            
        result["kategoriler"][cat_id]["sablonlar"][tmpl] = data

    conn.close()
    return result

def save_settings_node(node_name, data):
    """(Örn: bulut_ayarlari) Tüm root seviyesindeki key'leri günceller."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO settings (key, value) 
                 VALUES (?, ?)
                 ON CONFLICT(key) 
                 DO UPDATE SET value=excluded.value''',
              (node_name, json.dumps(data, ensure_ascii=False)))



    conn.commit()
    conn.close()

def save_category(cat_id, label):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO categories (id, label) 
                 VALUES (?, ?)
                 ON CONFLICT(id) 
                 DO UPDATE SET label=excluded.label''',
              (cat_id, label))



    conn.commit()
    conn.close()

def save_template(category_id, filename, data):
    """Tek bir şablonun koordinatlarını ve özelliklerini veritabanına kaydeder/günceller."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO templates (category_id, filename, data) 
                 VALUES (?, ?, ?)
                 ON CONFLICT(category_id, filename) 
                 DO UPDATE SET data=excluded.data''',
              (category_id, filename, json.dumps(data, ensure_ascii=False)))



    conn.commit()
    conn.close()

def save_templates_bulk(templates_list):
    """Çoklu şablon kaydetme (Transaction ile).
    templates_list: [{'category': 'cat', 'filename': 'tmpl.png', 'data': {...}}, ...]
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # SQLite transaction begins automatically with first execute
        for t in templates_list:
            c.execute('''INSERT INTO templates (category_id, filename, data) 
                         VALUES (?, ?, ?)
                         ON CONFLICT(category_id, filename) 
                         DO UPDATE SET data=excluded.data''',
                      (t['category'], t['filename'], json.dumps(t['data'], ensure_ascii=False)))
        conn.commit()
        return True, len(templates_list)
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_template(category_id, filename):
    """Tek bir şablonu veritabanından kalıcı olarak siler."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM templates WHERE category_id=? AND filename=?", (category_id, filename))



    conn.commit()
    conn.close()
