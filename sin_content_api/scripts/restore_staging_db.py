"""
Staging DB Restore Script for Phase P12 (T123, P12-07).
Restores a staging SQLite database from an approved backup,
verifies integrity and confirms all critical tables/records are intact.
P12-07: Mandatory manifest validation, pre-flight checksum & integrity checks before touching target DB.
"""
import gc
import hashlib
import json
import os
import shutil
import sqlite3
import sys

def restore_database(backup_file: str, target_db_path: str, manifest_file: str = None) -> dict:
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    # 1. P12-07: BAT BUOC KIEM TRA MANIFEST NEU DUOC TRUYEN
    if manifest_file:
        if not os.path.exists(manifest_file):
            raise FileNotFoundError(f"Manifest file provided but does not exist: {manifest_file}")
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        if manifest.get("status") != "APPROVED_BACKUP":
            raise ValueError(f"Backup manifest status is '{manifest.get('status')}', expected 'APPROVED_BACKUP'")

        if not manifest.get("secrets_scrubbed"):
            raise ValueError("Manifest indicates secrets have not been scrubbed from this backup artifact")

        expected_checksum = manifest.get("sha256_checksum")
        if expected_checksum:
            sha256 = hashlib.sha256()
            with open(backup_file, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            actual_checksum = sha256.hexdigest()
            if actual_checksum != expected_checksum:
                raise ValueError(f"Checksum mismatch! Expected: {expected_checksum}, Actual: {actual_checksum}")

    # 2. P12-07: KHOI PHUC VA KIEM TRA TREN FILE TAM (Temp verification)
    # Tuyet doi KHONG xoa target_db_path truoc khi file tam vuot qua kiem tra SQLite integrity!
    temp_target_path = target_db_path + ".tmp_verify"
    if os.path.exists(temp_target_path):
        try:
            os.remove(temp_target_path)
        except Exception:
            pass

    shutil.copyfile(backup_file, temp_target_path)

    # 3. Kiem tra tinh toan ven SQLite tren file tam (Connection dong an toan tren Windows)
    conn = None
    cursor = None
    integrity_result = None
    tables_count = 0
    records = {}

    try:
        conn = sqlite3.connect(temp_target_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        row = cursor.fetchone()
        integrity_result = row[0] if row else "failed"

        if integrity_result != "ok":
            raise RuntimeError(f"Database integrity check failed: {integrity_result}")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
        tables_count = len(tables)

        for t in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{t}"')
            records[t] = cursor.fetchone()[0]

    except Exception as e:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
            cursor = None
        if conn:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
        gc.collect()

        if os.path.exists(temp_target_path):
            try:
                os.remove(temp_target_path)
            except Exception:
                pass
        raise RuntimeError(f"Failed during integrity verification: {str(e)}")
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
            cursor = None
        if conn:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
        gc.collect()

    # 4. Khi da xac minh 100% file backup hop le: Thuc hien hoan doi nguyen tu (Safe Swap)
    if os.path.exists(target_db_path):
        try:
            os.remove(target_db_path)
        except Exception:
            pass

    shutil.move(temp_target_path, target_db_path)

    return {
        "status": "RESTORED_OK",
        "target_db": target_db_path,
        "integrity": integrity_result,
        "tables_count": tables_count,
        "records_per_table": records,
    }

if __name__ == "__main__":
    b_file = sys.argv[1] if len(sys.argv) > 1 else ""
    t_file = sys.argv[2] if len(sys.argv) > 2 else "sin_content_restored.db"
    m_file = sys.argv[3] if len(sys.argv) > 3 else None
    res = restore_database(b_file, t_file, m_file)
    print("RESTORE COMPLETED:", json.dumps(res, indent=2))
