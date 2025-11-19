import socket
import threading
import json
from datetime import datetime
from pathlib import Path
import bcrypt  # <- thêm bcrypt

from version import __version__  # lấy version dùng chung

USERS_FILE = Path("users.json")


def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    # Tài khoản mẫu được sử dụng lần đầu
    users = {"admin": "admin123", "user1": "pass1", "user2": "pass2"}
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return users


def save_users(users):
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def send_json(sock, obj):
    try:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        sock.sendall(data)
    except Exception:
        pass


def iter_json_lines(sock):
    """
    Đọc từng gói JSON từ socket.
    - Bỏ qua dòng rỗng.
    - Nếu JSON không hợp lệ, trả về gói thông báo lỗi hệ thống.
    """
    with sock.makefile("r", encoding="utf-8", newline="\n") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {
                    "type": "system",
                    "text": f"JSON không hợp lệ: {line[:50]}...",
                }


class ChatServer:
    def __init__(self, host="127.0.0.1", port=5555):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.clients = {}          # {socket: username}
        self.user_sockets = {}     # {username: socket}
        self.users = load_users()
        self.lock = threading.Lock()

    # =====================================================
    # START / SHUTDOWN
    # =====================================================
    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen()
        print(f"[SERVER] Chạy trên {self.host}:{self.port}")

        while True:
            try:
                client_socket, address = self.server.accept()
            except OSError:
                # socket đã đóng khi shutdown()
                break

            print(f"[NEW] {address} đã kết nối")
            threading.Thread(
                target=self.handle_client,
                args=(client_socket,),
                daemon=True,
            ).start()

    def shutdown(self):
        """Đóng tất cả kết nối client + socket server một cách an toàn."""
        print("[SERVER] Đang đóng tất cả kết nối client...")
        with self.lock:
            for sock, uname in list(self.clients.items()):
                try:
                    send_json(
                        sock,
                        {
                            "type": "system",
                            "text": "Server đang tắt, bạn sẽ bị ngắt kết nối.",
                        },
                    )
                except Exception:
                    pass
                try:
                    sock.close()
                except Exception:
                    pass
            self.clients.clear()
            self.user_sockets.clear()

        try:
            self.server.close()
        except Exception:
            pass
        print("[SERVER] Đã đóng socket server.")

    # =====================================================
    # HANDLE CLIENT
    # =====================================================
    def handle_client(self, client_socket):
        username = None
        try:
            # Lấy gói đầu tiên
            first = next(iter_json_lines(client_socket), None)
            if not first:
                client_socket.close()
                return

            # -------- REGISTER (nếu có) --------
            if first.get("type") == "register":
                username = first.get("username", "").strip()
                password = first.get("password", "")
                ok, msg = self.handle_register(username, password)
                send_json(
                    client_socket,
                    {"type": "register_result", "ok": ok, "message": msg},
                )
                if not ok:
                    client_socket.close()
                    return

                # Cho phép người dùng tiếp tục đăng nhập bằng gói login
                first = next(iter_json_lines(client_socket), None)
                if not first:
                    client_socket.close()
                    return

            # -------- LOGIN --------
            if first.get("type") != "login":
                send_json(
                    client_socket,
                    {
                        "type": "login_result",
                        "ok": False,
                        "message": "Thiếu gói login",
                    },
                )
                client_socket.close()
                return

            username = first.get("username", "").strip()
            password = first.get("password", "")
            ok, msg = self.handle_login(username, password)
            send_json(
                client_socket,
                {"type": "login_result", "ok": ok, "message": msg},
            )
            if not ok:
                client_socket.close()
                return

            # ❗ IF LOGIN FAIL → NGẮT LUÔN
            if not ok:
                client_socket.close()
                return

            # ĐĂNG NHẬP THÀNH CÔNG
            with self.lock:
                self.clients[client_socket] = username
                self.user_sockets[username] = client_socket

            self.broadcast_system(
                f"[{username}] đã tham gia phòng chat!", exclude=username
            )
            self.send_presence()

            # -------- Vòng lặp nhận tin --------
            for packet in iter_json_lines(client_socket):
                ptype = packet.get("type")

                if ptype == "chat":
                    text = str(packet.get("text", "")).strip()
                    if not text:
                        continue
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.broadcast(
                        {
                            "type": "chat",
                            "from": username,
                            "text": text,
                            "ts": ts,
                        },
                        exclude=None,
                    )

                # ----- DM (tin nhắn riêng) -----
                elif ptype == "dm":
                    to_user = str(packet.get("to", "")).strip()
                    text = str(packet.get("text", "")).strip()
                    if not to_user or not text:
                        continue
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.send_dm(
                        from_user=username,
                        to_user=to_user,
                        obj={
                            "type": "dm",
                            "from": username,
                            "to": to_user,
                            "text": text,
                            "ts": ts,
                        },
                    )

                    if not to_user:
                        send_json(client_socket, {"type": "system", "text": "Bạn chưa chọn người nhận."})
                        continue

                    if to_user not in self.user_sockets:
                        send_json(client_socket, {"type": "system", "text": f"User '{to_user}' không online."})
                        continue

                    ts = datetime.now().strftime("%H:%M:%S")

                    obj = {
                        "type": "dm",
                        "from": username,
                        "to": to_user,
                        "text": text,
                        "ts": ts
                    }

                    self.send_dm(username, to_user, obj)

                # ----- quit -----
                elif ptype == "quit":
                    break

                else:
                    send_json(
                        client_socket,
                        {
                            "type": "system",
                            "text": f"Loại gói không hỗ trợ: {ptype}",
                        },
                    )

        except Exception as e:
            print(f"[ERROR] {e}")

        finally:
            # cleanup
            with self.lock:
                if client_socket in self.clients:
                    uname = self.clients.pop(client_socket)
                    self.user_sockets.pop(uname, None)
                else:
                    uname = username

            try:
                client_socket.close()
            except Exception:
                pass

            if uname:
                self.broadcast_system(
                    f"[{uname}] đã rời khỏi phòng chat!", exclude=None
                )
                self.send_presence()

    # =====================================================
    # AUTH HELPERS
    # =====================================================
    def handle_register(self, username, password):
        if not username or not password:
            return False, "Thiếu username/password"

        with self.lock:
            if username in self.users:
                return False, "Tên đã tồn tại"

            # (ở branch này vẫn dùng plaintext; branch #9 dùng bcrypt)
            self.users[username] = password
            save_users(self.users)

        print(f"[REGISTER] {username} đã đăng ký")
        return True, "Đăng ký thành công"

    def handle_login(self, username, password):
        stored = self.users.get(username)
        if stored is None:
            return False, "Sai tài khoản hoặc mật khẩu"

        with self.lock:
            if username in self.user_sockets:
                return False, "Tài khoản đang đăng nhập ở nơi khác"

        return True, "Đăng nhập thành công"

    # =====================================================
    # BROADCAST / PRESENCE / DM
    # =====================================================
    def broadcast(self, message, exclude=None):
        """
        Gửi message (dict JSON) tới tất cả client đang kết nối.
        - exclude: tên người dùng để bỏ qua khi gửi (không gửi cho họ)
        """
        with self.lock:
            targets = list(self.clients.items())  # [(socket, username), ...]

        for sock, uname in targets:
            if exclude and uname == exclude:
                continue
            try:
                send_json(sock, message)
            except Exception:
                pass

    def broadcast_system(self, text, exclude=None):
        self.broadcast({"type": "system", "text": text}, exclude)

    def send_presence(self):
        with self.lock:
            online = list(self.user_sockets.keys())
        self.broadcast({"type": "presence", "users": online})

    def send_dm(self, from_user, to_user, obj):
        """
        Gửi tin nhắn riêng (DM) từ from_user tới to_user.
        Đồng thời gửi bản sao cho from_user để họ thấy tin đã gửi.
        """
        with self.lock:
            to_sock = self.user_sockets.get(to_user)
            from_sock = self.user_sockets.get(from_user)

        if to_sock:
            try:
                send_json(to_sock, obj)
            except Exception:
                pass

        if from_sock:
            try:
                send_json(from_sock, obj)
            except Exception:
                pass


if __name__ == "__main__":
    print("=" * 50)
    print(f"CHAT SERVER v{__version__} (register/login + public + DM)")
    print("=" * 50)
    server = ChatServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Nhận Ctrl+C, đang tắt server...")
        server.shutdown()
    finally:
        print("[SERVER] Đã tắt xong.")
