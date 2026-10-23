# Script cap nhat logo va sinh toan bo bo icon/favicon cho web SIN Creator OS
# PRJ_069_Sin_Xay_kenh

$rootPath = "C:\PRJ_069_Sin_Xay_kenh"
$sourceLogo = Join-Path $rootPath "logo.png"
$webPath = Join-Path $rootPath "03_ban_lam_viec\sin_creator_os"
$publicPath = Join-Path $webPath "public"
$appPath = Join-Path $webPath "src\app"

if (-not (Test-Path $sourceLogo)) {
    Write-Host "[!] Khong tim thay file logo nguon tai: $sourceLogo"
    exit 1
}

if (-not (Test-Path $publicPath)) {
    New-Item -ItemType Directory -Path $publicPath -Force | Out-Null
    Write-Host "[+] Da tao thu muc public tai: $publicPath"
}

Write-Host "[*] Dang bat dau chuyen doi va dong bo logo he thong..."

# 1. Tao file PNG chuan 32-bit RGBA cho public/logo.png
Write-Host "[*] 1/7 Sinh public/logo.png..."
cmd /c "ffmpeg -y -i ""$sourceLogo"" -vframes 1 -pix_fmt rgba ""$publicPath\logo.png"" >nul 2>&1"

# 2. Tao file WebP cho public/logo.webp
Write-Host "[*] 2/7 Sinh public/logo.webp..."
cmd /c "ffmpeg -y -i ""$sourceLogo"" -vframes 1 ""$publicPath\logo.webp"" >nul 2>&1"

# 3. Tao file vuong 512x512 transparent cho public/logo-square.png va public/icon.png
Write-Host "[*] 3/7 Sinh public/logo-square.png va public/icon.png (512x512)..."
$filterSquare512 = "scale=iw*min(512/iw\,512/ih):ih*min(512/iw\,512/ih),pad=512:512:(512-iw)/2:(512-ih)/2:color=0x00000000"
cmd /c "ffmpeg -y -i ""$sourceLogo"" -vf ""$filterSquare512"" -vframes 1 -pix_fmt rgba ""$publicPath\logo-square.png"" >nul 2>&1"
Copy-Item "$publicPath\logo-square.png" "$publicPath\icon.png" -Force
Copy-Item "$publicPath\logo-square.png" "$appPath\icon.png" -Force

# 4. Tao Apple Touch Icon (180x180)
Write-Host "[*] 4/7 Sinh apple-touch-icon.png (180x180)..."
$filterSquare180 = "scale=iw*min(180/iw\,180/ih):ih*min(180/iw\,180/ih),pad=180:180:(180-iw)/2:(180-ih)/2:color=0x00000000"
cmd /c "ffmpeg -y -i ""$sourceLogo"" -vf ""$filterSquare180"" -vframes 1 -pix_fmt rgba ""$publicPath\apple-touch-icon.png"" >nul 2>&1"
Copy-Item "$publicPath\apple-touch-icon.png" "$appPath\apple-icon.png" -Force

# 5. Tao Favicon ICO da do phan giai (32x32)
Write-Host "[*] 5/7 Sinh favicon.ico..."
$filterSquare32 = "scale=iw*min(32/iw\,32/ih):ih*min(32/iw\,32/ih),pad=32:32:(32-iw)/2:(32-ih)/2:color=0x00000000"
cmd /c "ffmpeg -y -i ""$sourceLogo"" -vf ""$filterSquare32"" -vframes 1 ""$publicPath\favicon.ico"" >nul 2>&1"
Copy-Item "$publicPath\favicon.ico" "$appPath\favicon.ico" -Force

# 6. Tao OpenGraph & Twitter Social Image (1200x630)
Write-Host "[*] 6/7 Sinh opengraph-image.png va twitter-image.png (1200x630)..."
cmd /c "ffmpeg -y -f lavfi -i color=c=#0b0f17:s=1200x630 -i ""$sourceLogo"" -filter_complex ""[1:v]scale=-1:440[logo];[0:v][logo]overlay=(W-w)/2:(H-h)/2"" -vframes 1 ""$appPath\opengraph-image.png"" >nul 2>&1"
Copy-Item "$appPath\opengraph-image.png" "$appPath\twitter-image.png" -Force

# 7. Cap nhat alt text
Write-Host "[*] 7/7 Cap nhat mo ta hinh anh OpenGraph..."
Set-Content -Path "$appPath\opengraph-image.alt.txt" -Value "BAHA Creator Studio Logo" -Encoding utf8
Set-Content -Path "$appPath\twitter-image.alt.txt" -Value "BAHA Creator Studio Logo" -Encoding utf8

Write-Host "[+] Hoan tat tao toan bo bo nhan dien logo va favicon web thanh cong!"
