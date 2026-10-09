import sqlite3
import json
import os
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2]


def resolve_runtime_root(source_root: Path = SOURCE_ROOT) -> Path:
    override = str(os.environ.get("MOCKUP_RUNTIME_WORKSPACE") or "").strip()
    return (
        Path(override).expanduser().resolve()
        if override
        else source_root.resolve()
    )


RUNTIME_ROOT = resolve_runtime_root()
# Mutable DB belongs to the runtime workspace; code stays in the source checkout.
DB_PATH = os.fspath(RUNTIME_ROOT / "SABLON_V2_MIMARI" / "ayarlar.db")

def get_db_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    # WAL lets the review UI write approvals while read-only factory/preflight
    # queries are active without unnecessary "database is locked" failures.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn

def _template_uid_has_legacy_unique_constraint(conn) -> bool:
    """Return True when an old DB still enforces UNIQUE(template_uid).

    EPIC-3 keeps source-version history for a template_uid, so multiple rows
    with the same UID are valid as long as only the current row is active.
    Older runtime DBs used UNIQUE(template_uid), which makes source replacement
    fail during re-analysis with "UNIQUE constraint failed".
    """
    c = conn.cursor()
    for index_row in c.execute("PRAGMA index_list(template_profiles)").fetchall():
        # PRAGMA index_list columns: seq, name, unique, origin, partial.
        if not int(index_row[2] or 0):
            continue
        index_name = str(index_row[1] or "")
        if not index_name:
            continue
        quoted_name = index_name.replace('"', '""')
        cols = [
            row[2]
            for row in c.execute(
                f'PRAGMA index_info("{quoted_name}")'
            ).fetchall()
        ]
        if cols == ["template_uid"]:
            return True
    return False


def _rebuild_template_profiles_without_uid_unique(conn):
    """Rebuild legacy template_profiles while preserving every existing row."""
    c = conn.cursor()
    legacy_columns = {
        row[1]
        for row in c.execute("PRAGMA table_info(template_profiles)").fetchall()
    }

    c.execute("DROP TABLE IF EXISTS template_profiles__epic3_migration")
    c.execute(
        """CREATE TABLE template_profiles__epic3_migration (
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
           )"""
    )

    canonical_columns = [
        "id",
        "template_uid",
        "category",
        "source_relative_path",
        "source_asset_sha256",
        "profile_version",
        "analyzer_version",
        "product_class",
        "orientation",
        "nominal_aspect",
        "geometry_type",
        "print_policy",
        "surface_quad",
        "outer_quad",
        "surface_mask_path",
        "material",
        "has_frame",
        "has_mat",
        "has_reflection",
        "has_occlusion",
        "confidence_total",
        "component_confidences",
        "review_status",
        "manually_verified",
        "is_active",
        "updated_at",
    ]

    insert_columns = []
    select_expressions = []
    for column in canonical_columns:
        if column == "id":
            insert_columns.append("id")
            select_expressions.append("id" if "id" in legacy_columns else "rowid")
        elif column in legacy_columns:
            insert_columns.append(column)
            select_expressions.append(column)

    if insert_columns:
        c.execute(
            f"""INSERT INTO template_profiles__epic3_migration
                    ({", ".join(insert_columns)})
                SELECT {", ".join(select_expressions)}
                FROM template_profiles"""
        )

    c.execute("DROP TABLE template_profiles")
    c.execute(
        "ALTER TABLE template_profiles__epic3_migration "
        "RENAME TO template_profiles"
    )


def migrate_schema(conn):
    """Single idempotent schema migration point for all runtime DB versions."""
    c = conn.cursor()
    migrations = [
        ("nominal_aspect", "ALTER TABLE template_profiles ADD COLUMN nominal_aspect TEXT"),
        ("is_active", "ALTER TABLE template_profiles ADD COLUMN is_active INTEGER DEFAULT 1"),
    ]

    # Inspect schema metadata instead of probing columns with SELECT ... LIMIT 1.
    # A successful SELECT that is not fetched leaves an active read cursor on
    # template_profiles; rebuilding that same table in this transaction then
    # fails with "database table is locked" on real upgraded runtime DBs.
    existing_columns = {
        row[1]
        for row in c.execute("PRAGMA table_info(template_profiles)").fetchall()
    }
    for col_name, alter_sql in migrations:
        if col_name not in existing_columns:
            c.execute(alter_sql)
            existing_columns.add(col_name)

    # Legacy databases may still have UNIQUE(template_uid). EPIC-3 deliberately
    # stores stale + current source-version rows under the same template_uid, so
    # that constraint must be removed without deleting historical evidence.
    if _template_uid_has_legacy_unique_constraint(conn):
        _rebuild_template_profiles_without_uid_unique(conn)


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
    
    c.execute('''CREATE TABLE IF NOT EXISTS template_number_registry (
                    category TEXT NOT NULL,
                    template_number INTEGER NOT NULL,
                    canonical_name TEXT,
                    first_seen_source TEXT,
                    first_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (category, template_number)
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

    # Persistent background jobs survive browser refreshes and app restarts.
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    progress_current INTEGER NOT NULL DEFAULT 0,
                    progress_total INTEGER NOT NULL DEFAULT 0,
                    progress_message TEXT,
                    result_json TEXT,
                    error_text TEXT,
                    stop_requested INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    started_at DATETIME,
                    finished_at DATETIME,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                 )''')
    c.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_status_created "
        "ON jobs(status, created_at)"
    )

    # Backend-level lease locks serialize destructive/mutating operations for
    # the same category/template across UI requests and background jobs.
    c.execute('''CREATE TABLE IF NOT EXISTS template_operation_locks (
                    category TEXT NOT NULL,
                    template TEXT NOT NULL,
                    owner_token TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    acquired_epoch REAL NOT NULL,
                    expires_epoch REAL NOT NULL,
                    PRIMARY KEY (category, template)
                 )''')

    # Pure AUTO analyzer cache. The key deliberately includes category,
    # source bytes and analyzer version so source/algorithm changes invalidate
    # old results automatically.
    c.execute('''CREATE TABLE IF NOT EXISTS analysis_cache (
                    category TEXT NOT NULL,
                    source_asset_sha256 TEXT NOT NULL,
                    analyzer_version TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (
                        category,
                        source_asset_sha256,
                        analyzer_version
                    )
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
        try:
            result[row["key"]] = json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            # One malformed optional setting must not make the complete editor
            # database unreadable.
            continue
        
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
        try:
            data = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        
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
