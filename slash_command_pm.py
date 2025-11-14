import tkinter as tk
from tkinter import messagebox

def send_message(self):
        if not self.connected or not self.client_socket:
            messagebox.showwarning("Chưa kết nối", "Bạn chưa kết nối tới server.")
            return

        msg = self.message_entry.get().strip()
        if not msg:
            return

        try:
            # Nếu đã chọn PM target
            if self.pm_target:
                self.send_json({"type": "dm", "to": self.pm_target, "text": msg})
                self.safe_append(f"[PM tới {self.pm_target}]: {msg}\n", "pm_me")

            # Nếu dùng lệnh /pm hoặc /dm
            elif msg.startswith("/pm ") or msg.startswith("/dm "):
                parts = msg.split(maxsplit=2)
                if len(parts) < 3:
                    self.safe_append("[Hệ thống]: Cú pháp đúng: /pm <user> <nội dung>\n", "sys")
                    return

                _, to_user, text = parts
                self.send_json({"type": "dm", "to": to_user, "text": text})
                self.safe_append(f"[PM tới {to_user}]: {text}\n", "pm_me")

            # Chat công khai
            else:
                self.send_json({"type": "chat", "text": msg})
                self.safe_append(f"[Bạn]: {msg}\n", "me")

            self.message_entry.delete(0, tk.END)

        except Exception as e:
            self.safe_append(f"[Hệ thống]: Lỗi khi gửi tin nhắn: {e}\n", "sys")

        except Exception as e:
            self.safe_append(f"[Hệ thống]: Lỗi khi gửi tin nhắn: {e}\n", "sys")
