# Changelog

Ghi lại những thay đổi đáng chú ý của dự án.

## [0.2.0] - 2025-11-19
- Hash mật khẩu bằng bcrypt và tự động migrate `users.json` từ plaintext.
- Cải thiện client: xử lý đóng app (`on_close`), sắp xếp lại luồng login / register.

## [0.1.0] - 2025-11-01
- Khởi tạo Chat App (TCP + JSON Lines, Tkinter client).
- Hỗ trợ đăng ký / đăng nhập, chat công khai, tin nhắn riêng (DM), danh sách người online.
