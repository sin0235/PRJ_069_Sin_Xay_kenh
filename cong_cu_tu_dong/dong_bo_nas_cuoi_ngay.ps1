param(
    [string]$ThuMucNas = 'Z:\01_du_an\PRJ_069_Sin_Xay_kenh',
    [switch]$XemTruoc
)

$ErrorActionPreference = 'Stop'
$nguon = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dich = Join-Path $ThuMucNas '03_ban_lam_viec'
$apiNguon = Join-Path $nguon 'sin_content_api'
$apiDich = Join-Path $dich 'sin_content_api'
$tepEnv = Join-Path $apiNguon '.env'
$tepEnvGoc = Join-Path (Split-Path -Parent $nguon) '.env'
$maDongBo = Get-Date -Format 'yyyyMMdd_HHmmss'
$tamDongBo = Join-Path $env:TEMP "prj069_sync_$maDongBo"
$thuMucLui = Join-Path $ThuMucNas "90_sao_luu\01_moc_khoi_phuc\sync_chuyen_may_$maDongBo"

function Get-GiaTriEnv([string]$DuongDan, [string]$Ten) {
    $dong = Get-Content -LiteralPath $DuongDan -Encoding utf8 | Where-Object { $_ -match "^\s*$Ten\s*=" } | Select-Object -First 1
    if (-not $dong) { return $null }
    $giaTri = ($dong -replace '^\s*[^=]+=', '').Trim()
    if ($giaTri.Length -ge 2 -and (($giaTri.StartsWith('"') -and $giaTri.EndsWith('"')) -or ($giaTri.StartsWith("'") -and $giaTri.EndsWith("'")))) {
        $giaTri = $giaTri.Substring(1, $giaTri.Length - 2)
    }
    return $giaTri
}

function Get-DatabaseNguon([string]$TenBien, [string[]]$TenChoPhep) {
    $url = Get-GiaTriEnv $tepEnv $TenBien
    if (-not $url.StartsWith('sqlite:///')) { throw "$TenBien phải trỏ tới SQLite cục bộ trong gói chuyển máy." }
    $tenTep = Split-Path ($url.Substring(10).Replace('/', '\')) -Leaf
    if ($tenTep -notin $TenChoPhep) { throw "$TenBien trỏ tới database chưa được cho phép: $tenTep" }
    $duongDan = Join-Path $apiNguon $tenTep
    if (-not (Test-Path -LiteralPath $duongDan -PathType Leaf)) { throw "Không thấy database đang cấu hình: $duongDan" }
    return (Resolve-Path -LiteralPath $duongDan).Path
}

function Save-SqliteSnapshot([string]$NguonDb, [string]$DichDb) {
    $thuMuc = Split-Path -Parent $DichDb
    New-Item -ItemType Directory -Force -Path $thuMuc | Out-Null
    if (Test-Path -LiteralPath $DichDb) { Remove-Item -LiteralPath $DichDb -Force }
    $maPython = 'import sqlite3,sys; src=sqlite3.connect(sys.argv[1],timeout=60); dst=sqlite3.connect(sys.argv[2],timeout=60); src.backup(dst,pages=512,sleep=0.25); dst.close(); src.close()'
    & python -c $maPython $NguonDb $DichDb
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $DichDb -PathType Leaf)) {
        throw "Không tạo được snapshot SQLite từ $NguonDb"
    }
}

if (-not (Test-Path -LiteralPath $ThuMucNas -PathType Container)) {
    throw "Không tìm thấy thư mục NAS: $ThuMucNas. Hãy kết nối ổ Z: rồi chạy lại."
}
if (-not (Test-Path -LiteralPath $tepEnv -PathType Leaf)) { throw "Thiếu cấu hình runtime: $tepEnv" }
$databaseNguon = @()
$databaseNguon += Get-DatabaseNguon -TenBien 'DATABASE_URL' -TenChoPhep @('sin_content_e2e_test.db')
$databaseNguon += Get-DatabaseNguon -TenBien 'BAHA_AUTH_DATABASE_URL' -TenChoPhep @('baha_auth_e2e_test.db')
$routerEnvNguon = Join-Path (Split-Path -Parent $nguon) '9router.env'
if (-not (Test-Path -LiteralPath $routerEnvNguon -PathType Leaf)) { throw "Thiếu cấu hình cổng 9Router: $routerEnvNguon" }
$tepDuAnGoc = Split-Path -Parent $nguon
$tepGocDongBo = @(
    '00_CHAY_DEV_MODE_SIN.cmd', '00_CHAY_GIAO_DIEN_SIN.cmd',
    '00_DANG_NHAP_GOOGLE_FLOW.cmd', '00_DANG_NHAP_TIKTOK.cmd',
    '00_KIEM_TRA_GOOGLE_FLOW.cmd', '00_MO_PROTOTYPE_G1.cmd',
    '00_MO_TRANG_THAI_DU_AN.cmd', '00_MO_HANH_TRINH_DU_AN.cmd', '00_MO_CHECKPOINT.cmd',
    '00_bat_dau/CURRENT_STATE.md', '00_bat_dau/CHECKPOINT.json',
    'hanh_trinh_phat_trien_069.html',
    '08_kiem_thu/bang_chung/dong_bo_nas_chuyen_may_20261026.md'
)
foreach ($relative in $tepGocDongBo) {
    if (-not (Test-Path -LiteralPath (Join-Path $tepDuAnGoc $relative) -PathType Leaf)) {
        throw "Thiếu tệp điều phối/chạy hệ thống: $relative"
    }
}

$loaiTruThuMuc = @(
    '.git', '.next', '.nuxt', '.venv', 'venv', 'env', 'node_modules', '.idea', '.vscode',
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.cache',
    'coverage', 'htmlcov', 'dist', 'build', 'out', '.vercel',
    'playwright-report', 'test-results', 'flow_downloads', 'flow_images', 'flow_videos'
)
$loaiTruTep = @(
    '.env*', '*.pyc', '*.pyo', '*.tsbuildinfo', '*.log', '*.swp', '*.swo', '.DS_Store',
    '*.db', '*.sqlite', '*.sqlite3', '*.wal', '*.shm', '*.mp4', '*.mov', '*.mkv',
    '*.avi', '*.webm', '*.mp3', '*.wav', '*.aac', '*.flac', '*.zip', '*.7z', '*.rar',
    '*.pem', '*.key', '*.p12', '*.pfx', 'id_rsa*', '*.token', '*.bearer',
    'flow_config.json', 'next-env.d.ts'
)
$tuyChon = @('/E', '/COPY:DAT', '/DCOPY:DAT', '/XJ', '/FFT', '/R:2', '/W:3', '/NP', '/NFL', '/NDL', '/TEE', '/MT:8')
$tuyChon += @('/XD') + $loaiTruThuMuc + @('/XF') + $loaiTruTep
if ($XemTruoc) { $tuyChon += '/L' }

Write-Host "Nguồn: $nguon"
Write-Host "Đích:  $dich"
Write-Host "Database đang dùng: $([IO.Path]::GetFileName($databaseNguon[0])), $([IO.Path]::GetFileName($databaseNguon[1]))"
Write-Host 'Kèm cấu hình runtime hiện có: .env gốc, sin_content_api/.env, mẫu .env.example và 9router.env; không ghi nội dung bí mật ra log.'
Write-Host 'Kèm dữ liệu: media_assets (cộng dồn, không xóa tệp trên NAS).'
if ($XemTruoc) { Write-Host 'Chế độ xem trước: không sao chép dữ liệu.' }
else { Write-Host "Đồng bộ cộng dồn; bản NAS cũ được lưu tại: $thuMucLui" }

if (-not $XemTruoc) {
    New-Item -ItemType Directory -Force -Path $tamDongBo | Out-Null
    New-Item -ItemType Directory -Force -Path $thuMucLui | Out-Null
    $databaseTam = @()
    for ($i = 0; $i -lt $databaseNguon.Count; $i++) {
        $snapshot = Join-Path $tamDongBo (Split-Path $databaseNguon[$i] -Leaf)
        Save-SqliteSnapshot $databaseNguon[$i] $snapshot
        $databaseTam += $snapshot
    }
    foreach ($relative in @('.env', 'sin_content_api/.env', 'sin_content_api/.env.example', '9router.env')) {
        $old = Join-Path $ThuMucNas $relative
        if (Test-Path -LiteralPath $old -PathType Leaf) {
            $backup = Join-Path $thuMucLui $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
            Copy-Item -LiteralPath $old -Destination $backup -Force
        }
    }
    foreach ($dbName in @('sin_content_e2e_test.db', 'baha_auth_e2e_test.db')) {
        $old = Join-Path $apiDich $dbName
        if ((Test-Path -LiteralPath "$old-wal") -or (Test-Path -LiteralPath "$old-shm")) {
            throw "Database đích đang có sidecar WAL/SHM; dừng dịch vụ chạy từ NAS trước khi đồng bộ: $dbName"
        }
        if (Test-Path -LiteralPath $old -PathType Leaf) {
            Save-SqliteSnapshot $old (Join-Path $thuMucLui "sin_content_api\$dbName")
        }
    }
    foreach ($relative in $tepGocDongBo) {
        $old = Join-Path $ThuMucNas $relative
        if (Test-Path -LiteralPath $old -PathType Leaf) {
            $backup = Join-Path $thuMucLui $relative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backup) | Out-Null
            Copy-Item -LiteralPath $old -Destination $backup -Force
        }
    }
}

& robocopy $nguon $dich @tuyChon
$maThoat = $LASTEXITCODE
if ($maThoat -ge 8) {
    throw "Robocopy thất bại với mã $maThoat. Kiểm tra kết nối NAS và quyền ghi."
}
if (-not $XemTruoc) {
    $mediaNguon = Join-Path $nguon 'media_assets'
    if (Test-Path -LiteralPath $mediaNguon -PathType Container) {
        & robocopy $mediaNguon (Join-Path $dich 'media_assets') /E /COPY:DAT /DCOPY:DAT /XJ /FFT /R:2 /W:3 /NP /TEE /NFL /NDL /MT:8
        if ($LASTEXITCODE -ge 8) { throw "Đồng bộ media_assets thất bại với mã $LASTEXITCODE" }
    }
    Copy-Item -LiteralPath $tepEnv -Destination (Join-Path $apiDich '.env') -Force
    Copy-Item -LiteralPath (Join-Path $apiNguon '.env.example') -Destination (Join-Path $apiDich '.env.example') -Force
    Copy-Item -LiteralPath $routerEnvNguon -Destination (Join-Path $ThuMucNas '9router.env') -Force
    if (Test-Path -LiteralPath $tepEnvGoc -PathType Leaf) {
        Copy-Item -LiteralPath $tepEnvGoc -Destination (Join-Path $ThuMucNas '.env') -Force
    }
    for ($i = 0; $i -lt $databaseTam.Count; $i++) {
        $dbName = Split-Path $databaseNguon[$i] -Leaf
        $nasDb = Join-Path $apiDich $dbName
        Copy-Item -LiteralPath $databaseTam[$i] -Destination $nasDb -Force
        foreach ($suffix in @('-wal', '-shm')) {
            $sidecar = "$nasDb$suffix"
            if (Test-Path -LiteralPath $sidecar) { Remove-Item -LiteralPath $sidecar -Force }
        }
        $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $databaseTam[$i]).Hash
        $destHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $nasDb).Hash
        if ($sourceHash -ne $destHash) { throw "Xác minh SHA-256 database thất bại: $dbName" }
    }
    foreach ($relative in $tepGocDongBo) {
        $targetFile = Join-Path $ThuMucNas $relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $targetFile) | Out-Null
        Copy-Item -LiteralPath (Join-Path $tepDuAnGoc $relative) -Destination $targetFile -Force
    }
    Remove-Item -LiteralPath $tamDongBo -Recurse -Force
    Write-Host "Database đã snapshot và xác minh SHA-256; cấu hình runtime đã đồng bộ."
}
Write-Host "Hoàn tất. Mã Robocopy: $maThoat"
