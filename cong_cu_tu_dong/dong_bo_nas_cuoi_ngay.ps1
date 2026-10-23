param(
    [string]$ThuMucNas = 'Z:\01_du_an\PRJ_069_Sin_Xay_kenh',
    [switch]$XemTruoc
)

$ErrorActionPreference = 'Stop'
$nguon = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$dich = Join-Path $ThuMucNas '03_ban_lam_viec'

if (-not (Test-Path -LiteralPath $ThuMucNas -PathType Container)) {
    throw "Không tìm thấy thư mục NAS: $ThuMucNas. Hãy kết nối ổ Z: rồi chạy lại."
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
$tuyChon = @('/E', '/COPY:DAT', '/DCOPY:DAT', '/XJ', '/FFT', '/R:2', '/W:3', '/NP', '/NFL', '/NDL', '/TEE')
$tuyChon += @('/XD') + $loaiTruThuMuc + @('/XF') + $loaiTruTep
if ($XemTruoc) { $tuyChon += '/L' }

Write-Host "Nguồn: $nguon"
Write-Host "Đích:  $dich"
if ($XemTruoc) { Write-Host 'Chế độ xem trước: không sao chép dữ liệu.' }
else { Write-Host 'Đồng bộ cộng dồn: không xóa tệp trên NAS.' }

& robocopy $nguon $dich @tuyChon
$maThoat = $LASTEXITCODE
if ($maThoat -ge 8) {
    throw "Robocopy thất bại với mã $maThoat. Kiểm tra kết nối NAS và quyền ghi."
}
Write-Host "Hoàn tất. Mã Robocopy: $maThoat"
