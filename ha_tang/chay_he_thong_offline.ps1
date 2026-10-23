# Lệnh khởi động toàn bộ hệ thống SIN Content Intelligence ở chế độ Offline (Single-Command Boot)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$apiDir = Join-Path $root "03_ban_lam_viec\sin_content_api"

Write-Output "=== KHỞI ĐỘNG HỆ THỐNG SIN CONTENT INTELLIGENCE (OFFLINE MODE) ==="
Write-Output "1. Kiểm tra môi trường Python..."
python --version

Write-Output "`n2. Áp dụng Database Migrations (Khởi tạo bảng)..."
python -c "import sys; sys.path.insert(0, r'$apiDir'); from src.migrations.runner import migration_up; print('Bảng dữ liệu:', migration_up())"

Write-Output "`n3. Kiểm tra kiểm thử sức khỏe (Healthz & Readyz)..."
python -c "import sys; sys.path.insert(0, r'$apiDir'); from src.database import check_db_ready; print('Database Ready:', check_db_ready())"

Write-Output "`n4. Khởi chạy máy chủ FastAPI..."
python (Join-Path $apiDir "scripts\run_server.py")
