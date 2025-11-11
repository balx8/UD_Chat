# Chat_client.py
import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText


class ChatClientApp:
    def __init__(self):
        # ---- single Tk root ----
        self.root = tk.Tk()
        self.root.title("Chat App")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # socket & state
        self.client_socket = None
        self.username = ""
        self.connected = False

        # build Login UI first
        self.build_login_ui()

    # =========================================================
    # helpers for JSON line protocol
    # =========================================================


def send_json(self, obj):
    """
    Gửi một đối tượng Python (dict) dưới dạng JSON qua socket client.
    - Mỗi gói kết thúc bằng ký tự xuống dòng '\n' để phía nhận tách gói dễ dàng.
    """
    try:
        # Chuyển dict thành chuỗi JSON (giữ nguyên Unicode)
        data_str = json.dumps(obj, ensure_ascii=False) + "\n"
        # Mã hóa UTF-8 để gửi qua socket
        data_bytes = data_str.encode("utf-8")
        # Gửi toàn bộ dữ liệu qua socket
        self.client_socket.sendall(data_bytes)
    except Exception as e:
        # Nếu lỗi, có thể log hoặc bỏ qua tùy yêu cầu
        # print(f"Lỗi khi gửi JSON: {e}")
        pass

    def iter_json_lines(self):
        f = self.client_socket.makefile("r", encoding="utf-8", newline="\n")
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"type": "system", "text": f"JSON không hợp lệ: {line[:50]}..."}

    # =========================================================
    # UI BUILDERS
    # =========================================================
    def build_login_ui(self):
        self.login_frame = tk.Frame(self.root, padx=16, pady=16)
        self.login_frame.pack(fill="both", expand=True)

        title = tk.Label(
            self.login_frame, text="Đăng nhập / Đăng ký - Chat App", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(0, 12))

        tk.Label(self.login_frame, text="Tên đăng nhập:").grid(
            row=1, column=0, sticky="e", pady=4, padx=(0, 8))
        tk.Label(self.login_frame, text="Mật khẩu:").grid(
            row=2, column=0, sticky="e", pady=4, padx=(0, 8))
        tk.Label(self.login_frame, text="Server (ip:port):").grid(
            row=3, column=0, sticky="e", pady=4, padx=(0, 8))

        self.entry_username = tk.Entry(self.login_frame, width=28)
        self.entry_password = tk.Entry(self.login_frame, show="*", width=28)
        self.entry_server = tk.Entry(self.login_frame, width=28)
        self.entry_username.grid(row=1, column=1, sticky="w", pady=4)
        self.entry_password.grid(row=2, column=1, sticky="w", pady=4)
        self.entry_server.grid(row=3, column=1, sticky="w", pady=4)

        self.entry_server.insert(0, "127.0.0.1:5555")
        self.entry_username.focus_set()

        self.btn_register = tk.Button(
            self.login_frame, text="Đăng ký", width=12, command=self.handle_register)
        self.btn_login = tk.Button(
            self.login_frame, text="Đăng nhập", width=12, command=self.handle_login)
        self.btn_register.grid(row=4, column=0, pady=(10, 0))
        self.btn_login.grid(row=4, column=1, pady=(10, 0), sticky="w")

        # Bắt sự kiện nhấn Enter (Return) trên cửa sổ root
        # Khi người dùng nhấn Enter, gọi phương thức handle_login()
        self.root.bind("<Return>", lambda e: self.handle_login())

    def build_chat_ui(self):
        # hủy login frame & bỏ bind Enter cũ để tránh TclError khi widget bị destroy
        self.root.unbind("<Return>")
        self.login_frame.destroy()

        self.root.title(f"Chat App - {self.username}")
        self.chat_frame = tk.Frame(self.root, padx=10, pady=10)
        self.chat_frame.pack(fill="both", expand=True)

        header = tk.Label(self.chat_frame, text=f"💬 Phòng Chat - Xin chào {self.username}!",
                          font=("Segoe UI", 12, "bold"))
        header.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        # left: messages
        tk.Label(self.chat_frame, text="Tin nhắn:").grid(
            row=1, column=0, sticky="w")
        self.chat_window = ScrolledText(
            self.chat_frame, height=18, width=80, state="disabled", wrap="word")
        self.chat_window.grid(row=2, column=0, columnspan=2,
                              sticky="nsew", padx=(0, 8))

        # right: online users
        tk.Label(self.chat_frame, text="👥 Online:").grid(
            row=1, column=2, sticky="w")
        self.users_list = tk.Listbox(self.chat_frame, height=18, width=24)
        self.users_list.grid(row=2, column=2, sticky="ns")
        # click đúp để bật/tắt chế độ PM tới user đang chọn
        self.pm_target = None
        self.users_list.bind("<Double-Button-1>", self.toggle_pm_target)

        # bottom: entry + send
        self.message_entry = tk.Entry(self.chat_frame)
        self.message_entry.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.message_entry.bind("<Return>", lambda e: self.send_message())

        self.pm_label = tk.Label(
            self.chat_frame, text="Chế độ: Công khai", fg="#555")
        self.pm_label.grid(row=3, column=1, sticky="w", padx=(8, 0))

        self.send_button = tk.Button(
            self.chat_frame, text="Gửi", width=10, command=self.send_message)
        self.send_button.grid(row=3, column=2, sticky="e", pady=(8, 0))

        # Cấu hình trọng số (weight) cho các hàng và cột trong chat_frame
        # - Hàng 2 sẽ mở rộng theo chiều dọc khi thay đổi kích thước cửa sổ
        self.chat_frame.rowconfigure(2, weight=1)

        # - Cột 0 sẽ mở rộng theo chiều ngang, chiếm không gian còn lại
        self.chat_frame.columnconfigure(0, weight=1)

        # - Cột 1 và cột 2 không mở rộng (giữ kích thước cố định)
        self.chat_frame.columnconfigure(1, weight=0)
        self.chat_frame.columnconfigure(2, weight=0)

        # configure tags once
        self.chat_window.configure(font=("Segoe UI", 10))
        self.chat_window.tag_config(
            "me", foreground="#1b76d1", font=("Segoe UI", 10, "bold"))
        self.chat_window.tag_config(
            "pm_me", foreground="#6a1b9a", font=("Segoe UI", 10, "bold"))
        self.chat_window.tag_config(
            "pm_in", foreground="#2e7d32", font=("Segoe UI", 10, "bold"))
        self.chat_window.tag_config(
            "sys", foreground="#888888", font=("Segoe UI", 9, "italic"))

        # start background receive thread
        threading.Thread(target=self.receive_messages, daemon=True).start()
        self.safe_append("[Hệ thống]: Đăng nhập thành công.\n", "sys")

    # =========================================================
    # LOGIN / REGISTER ACTIONS
    # =========================================================
    def _connect(self):
        server_str = self.entry_server.get().strip()
        if ":" in server_str:
            host, port = server_str.split(":", 1)
            host = host.strip()
            port = int(port.strip())
        else:
            host = server_str.strip()
            port = 5555

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((host, port))

    def handle_register(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning("Thiếu thông tin", "Hãy nhập Tên đăng nhập và Mật khẩu.")
            return
        try:
            self._connect()
            self.send_json({"type": "register", "username": username, "password": password})
            resp = next(self.iter_json_lines(), None)
            if not resp or resp.get("type") != "register_result":
                raise RuntimeError("Phản hồi đăng ký không hợp lệ")
            if not resp.get("ok"):
                self.client_socket.close()
                self.client_socket = None
                messagebox.showerror("Đăng ký thất bại", resp.get("message", "Không xác định"))
                return
            # Nếu đăng ký ok, tiếp tục login ngay
            self.username = username
            self.send_json({"type": "login", "username": username, "password": password})
            login_resp = next(self.iter_json_lines(), None)
            if login_resp and login_resp.get("ok"):
                self.connected = True
                self.build_chat_ui()
            else:
                self.client_socket.close()
                self.client_socket = None
                messagebox.showerror("Đăng nhập thất bại", (login_resp or {}).get("message", "Không xác định"))
        except Exception as e:
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            self.client_socket = None
            messagebox.showerror("Lỗi đăng ký", f"{e}")

    def handle_login(self):
        username = self.entry_username.get().strip()
        password = self.entry_password.get().strip()
        if not username or not password:
            messagebox.showwarning("Thiếu thông tin", "Hãy nhập Tên đăng nhập và Mật khẩu.")
            return

        try:
            self._connect()
            self.username = username
            self.send_json({"type": "login", "username": username, "password": password})
            resp = next(self.iter_json_lines(), None)
            if not resp or resp.get("type") != "login_result":
                raise RuntimeError("Phản hồi đăng nhập không hợp lệ")
            if not resp.get("ok"):
                self.client_socket.close()
                self.client_socket = None
                messagebox.showerror("Đăng nhập thất bại", resp.get("message", "Không xác định"))
                return

            self.connected = True
            self.build_chat_ui()

        except Exception as e:
            self.connected = False
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            self.client_socket = None
            messagebox.showerror("Không thể kết nối", f"Lỗi: {e}")

    # =========================================================
    # CHAT ACTIONS
    # =========================================================
    def toggle_pm_target(self, event=None):
        #  Nhấp đúp để bật/tắt người nhận tin nhắn riêng (PM target)
        try:
            sel = self.users_list.get(self.users_list.curselection())
        except:
            return
        # Bỏ qua nếu nhấp vào chính tài khoản của mình.
        if sel == self.username:
            self.pm_target = None
            self.pm_label.config(text="Chế độ: Công khai", fg="#555")
            return
        # toggle
        if self.pm_target == sel:
            self.pm_target = None
            self.pm_label.config(text="Chế độ: Công khai", fg="#555")
        else:
            self.pm_target = sel
            self.pm_label.config(text=f"Chế độ: Riêng → {sel}", fg="#6a1b9a")

    def send_message(self):
        if not self.connected or not self.client_socket:
            messagebox.showwarning("Chưa kết nối", "Bạn chưa kết nối tới server.")
            return

        msg = self.message_entry.get().strip()
        if not msg:
            return

        try:
            if self.pm_target:
                # DM theo mục tiêu đang chọn
                self.send_json({"type": "dm", "to": self.pm_target, "text": msg})
                self.safe_append(f"[PM tới {self.pm_target}]: {msg}\n", "pm_me")
            else:
                # nếu gõ lệnh /pm user msg thì cũng hỗ trợ
                if msg.startswith("/pm ") or msg.startswith("/dm "):
                    parts = msg.split(maxsplit=2)
                    if len(parts) < 3:
                        self.safe_append("[Hệ thống]: Cú pháp: /pm <user> <nội dung>\n", "sys")
                        return
                    _, to_user, text = parts
                    self.send_json({"type": "dm", "to": to_user, "text": text})
                    self.safe_append(f"[PM tới {to_user}]: {text}\n", "pm_me")
                else:
                    self.send_json({"type": "chat", "text": msg})
                    self.safe_append(f"[Bạn]: {msg}\n", "me")

            self.message_entry.delete(0, tk.END)
        except Exception as e:
            self.safe_append(f"[Hệ thống]: Lỗi khi gửi tin nhắn: {e}\n", "sys")

    def receive_messages(self):
        """Receive from server in a background thread. UI updates are marshalled to main thread with .after()."""
        try:
            for packet in self.iter_json_lines():
                ptype = packet.get("type")

                if ptype == "system":
                    self.root.after(0, lambda p=packet: self.safe_append(p["text"] + "\n", "sys"))

                elif ptype == "presence":
                    users = packet.get("users", [])
                    self.root.after(0, lambda u=users: self.update_online_users(u))

                elif ptype == "chat":
                    frm = packet.get("from")
                    text = packet.get("text")
                    ts = packet.get("ts", "")
                    line = f"[{ts}] {frm}: {text}\n" if ts else f"{frm}: {text}\n"
                    self.root.after(0, lambda l=line: self.safe_append(l))

                elif ptype == "dm":
                    frm = packet.get("from")
                    to = packet.get("to")
                    text = packet.get("text")
                    ts = packet.get("ts", "")
                    if frm != self.username and to == self.username:
                        line = f"[{ts}] [PM từ {frm}]: {text}\n" if ts else f"[PM từ {frm}]: {text}\n"
                        self.root.after(0, lambda l=line: self.safe_append(l, "pm_in"))
                    else:
                        line = f"[{ts}] [PM tới {to}]: {text}\n" if ts else f"[PM tới {to}]: {text}\n"
                        self.root.after(0, lambda l=line: self.safe_append(l, "pm_me"))

                # login_result/register_result hiếm khi đến đây vì xử lý trước UI
        except Exception as e:
            self.root.after(0, lambda: self.safe_append(f"[Hệ thống]: Lỗi nhận dữ liệu: {e}\n", "sys"))
        finally:
            self.connected = False
            if self.client_socket:
                try:
                    self.client_socket.close()
                except:
                    pass
            self.client_socket = None
            self.root.after(0, lambda: self.safe_append("[Hệ thống]: Mất kết nối tới server.\n", "sys"))

    # =========================================================
    # UI HELPERS
    # =========================================================
    def safe_append(self, text, tag=None):
        """Append text to chat window safely (must be called in main thread)."""
        self.chat_window.configure(state="normal")
        if tag:
            self.chat_window.insert("end", text, tag)
        else:
            self.chat_window.insert("end", text)
        self.chat_window.see("end")
        self.chat_window.configure(state="disabled")

    def update_online_users(self, users):
        self.users_list.delete(0, "end")
        for u in users:
            if u:
                self.users_list.insert("end", u)
        #Nếu người này đã là PM target hiện tại → hủy chọn (trở về chế độ công khai)
        if self.pm_target and self.pm_target not in users:
            self.pm_target = None
            self.pm_label.config(text="Chế độ: Công khai", fg="#555")

   # APP LIFECYCLE: Vòng đời ứng dụng
# Bao gồm các trạng thái và sự kiện mà ứng dụng trải qua từ khi khởi chạy đến khi đóng:
# - Khởi tạo (Init)
# - Hoạt động (Active / Running)
# - Tạm dừng (Paused / Background)
# - Dừng / Đóng (Stopped / Terminated)
# Quản lý vòng đời giúp xử lý tài nguyên, lưu trạng thái, và phản hồi sự kiện đúng thời điểm
    def on_close(self):
        try:
            if self.connected and self.client_socket:
                # Gửi tín hiệu "quit" để thoát một cách gọn gàng, server sẽ thực hiện cleanup
                self.send_json({"type": "quit"})
        except:
            pass
        try:
            if self.client_socket:
                self.client_socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    ChatClientApp().run()
