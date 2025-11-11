# Chat App (TCP + JSON Lines, Tkinter Client)

Ứng dụng chat client–server đơn giản dùng TCP socket với giao thức **JSON Lines**. Client viết bằng **Tkinter** (Python GUI), server thuần Python, hỗ trợ **đăng ký/đăng nhập**, **chat công khai**, **tin nhắn riêng (DM)**, và **danh sách người online**.

> Repo mẫu có 2 file chính:
>
> - `chat_server.py` – server TCP đa luồng, lưu user vào `users.json`.
> - `chat_client.py` – ứng dụng desktop (Tkinter) giao diện đăng nhập + cửa sổ chat.
>
> Chạy được trên Windows/macOS/Linux với Python ≥ 3.9.

---

## Tính năng chính

- Đăng ký & đăng nhập (tên/mật khẩu) với lưu trữ `users.json` tự động tạo lần đầu.
- Phòng chat công khai: mọi người nhận được tin nhắn ngay khi có.
- Tin nhắn riêng (DM) theo 2 cách:
  - Double‑click tên trong danh sách Online để bật/tắt chế độ PM đến người đó.
  - Gõ lệnh `/pm <user> <nội dung>`.
- Danh sách người dùng online cập nhật thời gian thực (gói `presence`).
- Phân luồng: server đa luồng cho mỗi kết nối; client có thread nền nhận tin và **marshal** cập nhật UI về main thread qua `root.after(...)` (tránh lỗi Tk).
- Giao thức **JSON Lines** đơn giản, thuần văn bản, dễ debug.

---

## Cấu trúc thư mục

```
.
├─ chat_server.py        # Server TCP đa luồng
├─ chat_client.py        # Ứng dụng Tkinter client
└─ users.json            # (tự tạo) CSDL tài khoản dạng JSON
```

---

## Yêu cầu hệ thống

- Python 3.9+
- Không cần thư viện ngoài (chỉ dùng chuẩn: `socket`, `threading`, `json`, `tkinter`…).
- Tkinter có sẵn trong đa số bản cài Python trên Windows/macOS. Trên một số distro Linux cần cài thêm gói `python3-tk`.

---

## Cách chạy nhanh (Quick Start)

1) **Tạo môi trường (khuyến nghị)**
```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

2) **Chạy server**
```bash
python chat_server.py
```
- Mặc định lắng nghe `127.0.0.1:5555`. Thay đổi host/port bằng cách sửa `ChatServer(host, port)` trong file.

3) **Chạy client**
```bash
python chat_client.py
```
- Ở màn hình login, nhập `Server (ip:port)` ví dụ `127.0.0.1:5555`.
- Có thể **Đăng ký** tài khoản mới, sau đó hệ thống tự đăng nhập.
- Hoặc **Đăng nhập** bằng tài khoản có sẵn.
- Tài khoản mẫu tạo sẵn (nếu chưa có `users.json`): `admin/admin123`, `user1/pass1`, `user2/pass2`.

> **Mẹo dùng nhanh**
> - Gõ tin và nhấn **Enter** để gửi công khai.
> - Double‑click tên trong **Online** để bật/tắt PM đến người đó.
> - Lệnh slash: `/pm <user> <nội dung>` gửi PM tức thời không cần bật chế độ PM.

---

## Giao thức: JSON Lines

Mỗi gói là một JSON **trên một dòng** (kết thúc bằng `\n`). Một số loại gói:

### Client → Server
- `{"type":"register","username":"u","password":"p"}`
- `{"type":"login","username":"u","password":"p"}`
- `{"type":"chat","text":"..."}`
- `{"type":"dm","to":"userB","text":"..."}"
- `{"type":"quit"}` – xin ngắt kết nối (server sẽ dọn dẹp)

### Server → Client
- Kết quả đăng ký: `{"type":"register_result","ok":true,"message":"..."}`
- Kết quả login: `{"type":"login_result","ok":true,"message":"..."}"
- Thông báo hệ thống: `{"type":"system","text":"..."}"
- Hiện diện (online): `{"type":"presence","users":["u1","u2", ...]}`
- Chat công khai: `{"type":"chat","from":"u","text":"...","ts":"HH:MM:SS"}`
- Tin nhắn riêng: `{"type":"dm","from":"uA","to":"uB","text":"...","ts":"HH:MM:SS"}`

> **Nguyên tắc xử lý**
> - Server phát (`broadcast`) tin `chat` cho mọi client.
> - `dm` được gửi cho người nhận và **bản sao** cho người gửi.
> - `presence` gửi định kỳ (mỗi khi có thay đổi) danh sách online.

---

## Luồng hoạt động

1. Client kết nối TCP → gửi `register` (tuỳ chọn) rồi `login`.
2. Server xác thực, lưu socket <→ username>, phát thông báo hệ thống, gửi `presence`.
3. Trong phiên, client gửi `chat`/`dm`; server chuyển tiếp và gắn timestamp.
4. Khi client đóng, gửi `quit` (tuỳ chọn), server thu hồi và cập nhật `presence`.

---

## Kiến trúc & các điểm đáng chú ý

### Server (`chat_server.py`)
- Dùng `threading.Thread` cho mỗi kết nối; `self.lock` bảo vệ các cấu trúc dùng chung (`clients`, `user_sockets`, `users`).
- Người dùng lưu trong `users.json`. Nếu file chưa tồn tại, tạo mặc định một số tài khoản mẫu.
- Chặn đăng nhập 2 nơi: nếu username đã có trong `user_sockets` thì từ chối.
- Định dạng thời gian `HH:MM:SS` thêm vào `chat`/`dm`.

### Client (`chat_client.py`)
- Một Tk root duy nhất, module hoá UI: **màn hình login** → **màn hình chat**.
- Thread nền đọc socket qua `iter_json_lines()`, mọi cập nhật UI đẩy về main thread bằng `root.after(...)`.
- Hỗ trợ DM bằng **toggle** trong Listbox hoặc slash command `/pm`.
- Tagging màu cho các loại tin: bạn, PM gửi/nhận, hệ thống.

---

## Bảo mật & đề xuất nâng cấp

Hiện tại project **đủ cho demo** nhưng chưa an toàn cho môi trường thật:

- Mật khẩu lưu **plaintext** trong `users.json`. Nên dùng **bcrypt/argon2** và **salt**.
- Giao tiếp thuần TCP không mã hóa. Nên dùng **TLS** (ví dụ: `ssl.wrap_socket(...)`) hoặc đặt sau reverse proxy bảo mật.
- Thêm **rate‑limit / anti‑brute‑force** cho đăng nhập.
- Thêm **CS**: kiểm tra độ dài/UTF‑8 hợp lệ, chặn JSON quá lớn.
- **Persist lịch sử** (SQLite/PostgreSQL); nén/rotate log.
- **Phòng/Room** (topic), **nhiều phòng**, **quyền admin**, **mute/ban**.
- **Reconnect** & **backoff**, **heartbeat/ping** để phát hiện đứt kết nối.
- **Thông báo desktop**, **gõ‑đang‑soạn (typing)**, **đã đọc**.
- **I18n**: tách text UI, hỗ trợ đa ngôn ngữ.

---

## Tuỳ biến & mở rộng

- **Đổi cổng/host**: sửa tham số `ChatServer(host, port)`.
- **Đổi font/màu UI**: các `tag_config` trong client.
- **Alias lệnh**: hiện có `/pm`, có thể thêm `/me`, `/help`, `/w`…
- **Tích hợp file**: có thể thêm gửi file qua TCP (chunk + metadata), hoặc chuyển sang WebSocket nếu muốn giao diện web.

---

## Khắc phục sự cố (Troubleshooting)

| Vấn đề | Nguyên nhân khả dĩ | Cách xử lý |
|---|---|---|
| Client báo “Không thể kết nối” | Server chưa chạy / sai IP:port / Firewall chặn | Kiểm tra server đang lắng nghe, đúng `127.0.0.1:5555`, tắt firewall nội bộ khi test |
| Đăng nhập thất bại | Sai mật khẩu hoặc user đã đăng nhập ở nơi khác | Đúng cred hoặc đợi phiên cũ hết; xóa dòng username trong `user_sockets` (restart server) |
| Gõ Enter không gửi | Focus không ở ô nhập / lỗi Tk event | Click vào ô nhập, thử lại; xem log console nếu có stacktrace |
| Không thấy người online | `presence` chưa gửi hoặc client không refresh | Xem log server; thử gửi tin nhắn hoặc disconnect/reconnect |
| Unicode lỗi/hiển thị lạ | JSON/encoding không UTF‑8 | Đảm bảo file đọc/ghi dùng `encoding="utf-8"` (đã có sẵn) |

---


## Ghi công

- Server & Client tham khảo/viết mới theo chuẩn thư viện chuẩn Python (`socket`, `threading`, `tkinter`).

Chúc bạn code vui vẻ! 🚀
