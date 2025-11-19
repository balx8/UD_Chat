# Hướng dẫn release

## 1. Chuẩn bị

- Code đã được merge vào `main`.
- Cập nhật `CHANGELOG.md` cho phiên bản mới.
- Test lại nhanh:
  - `python chat_server.py`
  - `python chat_client.py`
  - Đăng nhập, đăng ký, gửi tin nhắn.

## 2. Tạo tag

```bash
git switch main
git pull
git tag v0.2.0
git push origin v0.2.0
