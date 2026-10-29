# Hướng dẫn làm việc và triển khai PRJ_069 lên NAS

Ba nơi tách biệt, mỗi nơi có nguồn sự thật riêng:

| Nơi | Chứa gì | Ai được ghi |
|---|---|---|
| Máy này (worktree) | Code đang phát triển, thử nghiệm | Bạn và Claude |
| GitHub `sin0235/PRJ_069_Sin_Xay_kenh` | Code đã commit | Chỉ qua branch rồi Pull Request, không đẩy thẳng `main` |
| NAS | Code đã commit + image đã build + dữ liệu + bí mật | Chỉ qua `nas_release.py sync` |

Những thứ chỉ tồn tại trên NAS và không bao giờ vào git: `.env` / `deploy.env`, thư mục `secrets/`, các volume dữ liệu (`prj069-nas-data`, `prj069-nas-flow-profiles`, `prj069-nas-models`), token Cloudflare tunnel. Script đồng bộ không đụng vào chúng.

## 1. Làm việc trên máy này (không ảnh hưởng NAS và GitHub)

1. Tạo branch riêng hoặc worktree mới từ `main`, ví dụ `git worktree add ../prj069-viec-moi -b feat/ten-viec origin/main`. Không sửa trực tiếp trên `main`.
2. Sửa, chạy test cục bộ. Khi cần chạy stack cục bộ, dùng `deploy.env` riêng với `PRJ069_COMPOSE_PROJECT_NAME=prj069-nas` và các tên volume khác NAS; cổng mặc định `127.0.0.1:3069`.
3. Commit trên branch, rồi `git push -u origin <branch>` và mở Pull Request vào `main`.

Việc sửa code trên máy này không thay đổi NAS cho tới khi bạn chạy bước 2 bên dưới.

## 2. Triển khai lên NAS

Chạy từ thư mục gốc của repo, trên branch đã commit sạch (file đã theo dõi không có thay đổi chưa commit):

```sh
python3 ha_tang/nas_trien_khai_sach/nas_release.py sync --tag 20261030a --dry-run   # xem trước
python3 ha_tang/nas_trien_khai_sach/nas_release.py sync --tag 20261030a
```

`--tag` là nhãn image mới (ngày + chữ cái, mỗi lần triển khai một nhãn mới, không dùng lại). Lệnh `sync`:
- Lấy nội dung từ commit (mặc định `HEAD`), không đọc working tree. Từ chối chạy nếu còn thay đổi chưa commit.
- So với commit đã ghi trong `ha_tang/nas_trien_khai_sach/.deployed_ref` trên NAS, chỉ tải file đổi (thêm, sửa, xóa) thuộc phạm vi build (cùng danh sách với `.dockerignore`).
- Sinh `compose.yaml` cho NAS từ `compose.yaml` của repo: ghim image theo `--tag` và bỏ dòng `cpus` (kernel DSM không hỗ trợ CFS). Repo compose không bị sửa.
- Sinh thêm `nas_apply/compose.yaml` (project phụ `prj069-apply`) và ghi lại `.deployed_ref`.

Sau đó build và chạy lại stack bằng project phụ `prj069-apply` (dùng `docker.sock`, chỉ thao tác trên project `prj069-xaykenh-nhap`). Cách này tránh lỗi DSM bị lệch tên container khi bấm Stop/Build/Start liên tiếp:

1. Lần đầu duy nhất: DSM Container Manager, Project, Create. Tên `prj069-apply`. Path chọn share `09.ai_workspace` rồi `01_du_an/PRJ_069_Sin_Xay_kenh/03_ban_lam_viec/ha_tang/nas_trien_khai_sach/nas_apply`. Chọn dùng compose có sẵn.
2. Mỗi lần triển khai sau `sync`: chọn project `prj069-apply`, Action, Build (để DSM đọc lại compose mới), rồi Start. Project tự thoát khi xong.
3. Đọc kết quả ở `.../nas_apply/result.txt` (qua SMB hoặc File Station). Dòng cuối phải là `done`, `rc=0` ở các bước build và up, và các container `api`, `web`, `flow-session-worker`, `gateway` ở trạng thái healthy.
4. Kiểm tra: mở domain `https://nhap-xaykenh-prj069.bahagroup.vn`, đăng nhập, và `.../readyz` trả 200.

Bước build bằng helper (`docker compose build` với classic builder) chưa được chạy thử trên NAS. Nếu nó lỗi, build bằng DSM trên project `prj069-xaykenh-nhap` (Stop, Build) rồi để helper chạy lại vì lúc đó chỉ cần `up`. Các bước stop, xóa theo label và `up -d` đã được chạy thật.

## 3. Quay lại bản trước

Chạy `sync` với commit cũ và nhãn cũ, rồi lặp lại bước helper:

```sh
python3 ha_tang/nas_trien_khai_sach/nas_release.py sync --ref <commit-cu> --tag <nhan-cu>
```

Nếu image nhãn cũ còn trên NAS thì không phải build lại. Image cũ chỉ còn khi bạn chưa dọn: nên giữ ít nhất hai nhãn gần nhất, xóa các nhãn cũ hơn bằng DSM Container Manager, Image.

## 4. Những điều cần nhớ

- Không bấm Stop, Build, Start liên tiếp trong DSM khi thao tác trước chưa xong. Đây là nguyên nhân khả dĩ làm container bị "treo" (DSM giữ tên tạm có tiền tố, chưa được xác minh bằng log dockerd).
- Tunnel Cloudflare chạy ở project `prj069-cloudflared` riêng (`/docker/prj069_cloudflared`), không thuộc quy trình này. Token tunnel đã từng dán vào chat nên nên xoay vòng.
- Khi đổi domain hoặc origin: sửa `AUTH_ALLOWED_ORIGINS` và `AUTH_COOKIE_SECURE` trong `.env` trên NAS, rồi chạy lại helper. Chỉ có origin HTTPS thì dùng `AUTH_COOKIE_SECURE=true`.
- Dữ liệu thật nằm trong volume. Không chạy `docker compose down -v` và không đổi `PRJ069_BOOTSTRAP_MODE` thành `fresh` trên stack đang có dữ liệu.
- Sao lưu và khôi phục: xem `README.md` (lệnh `nas_runtime_ops.py backup` và `restore`).

## 5. Chưa được kiểm chứng

- `.deployed_ref` đầu tiên là mốc giả định rằng mã trên NAS khớp với commit ghi trong đó. Muốn chắc, so sánh hash file trên NAS với repo trước khi tin vào mốc này.
- Bước `sync` thật (tải lên NAS) chỉ mới được chạy thử ở chế độ `--dry-run`.
- Bước build qua helper chưa chạy thật như đã nói ở trên.
