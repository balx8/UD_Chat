import socket
import threading
import json
from datetime import datetime
from pathlib import Path
import bcrypt  # <- thêm bcrypt

USERS_FILE = Path("users.json")

# =====================================================
# =============== AUTH / BCRYPT HELPERS ===============
# =====================================================

def hash_password(password: str) -> str:
    """Hash mật khẩu bằng bcrypt, trả về string để lưu vào JSON."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, hashed: str) -> bool:
    """So sánh mật khẩu người dùng nhập với hash trong users.json."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Hash sai format -> coi như sai mật khẩu
        return False


def looks_like_bcrypt(s: str) -> bool:
    """Nhận diện chuỗi trông giống bcrypt hay không (dùng cho migrate)."""
    if not isinstance(s, str):
        return False
    return s.startswith("$2a$") or s.startswith("$2b$") or s.startswith("$2y$")


def migrate_plaintext_users(users: dict) -> dict:
    """
    Nếu users.json đang dạng {"admin": "admin123"} (plaintext)
    thì sẽ hash lại sang bcrypt và ghi đè file.
    """
    changed = False
    for username, value in list(users.items()):
        if isinstance(value, str) and not looks_like_bcrypt(value):
            # plaintext -> hash lại
            users[username] = hash_password(value)
            changed = True

    if changed:
        USERS_FILE.write_text(
            json.dumps(users, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print("[INFO] Migrated plaintext passwords in users.json to bcrypt.")

    return users

# =====================================================
# =============== JSON FUNCTIONS ======================
# =====================================================

def load_users():
    if USERS_FILE.exists():
        users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        # tự migrate nếu còn plaintext
        return migrate_plaintext_users(users)

    # Tạo tài khoản mẫu (dùng bcrypt luôn)
    users = {
        "admin": hash_password("admin123"),
        "user1": hash_password("pass1"),
        "user2": hash_password("pass2"),
    }
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return users


def save_users(users):
    USERS_FILE.write_text(
        json.dumps(users, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def send_json(sock, obj):
    try:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        sock.sendall(data)
    except:
        pass


def iter_json_packets(sock):
    """Đọc từng dòng JSON từ socket"""
    with sock.makefile("r", encoding="utf-8", newline="\n") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"type": "system", "text": "JSON không hợp lệ!"}

# =====================================================
# =============== CHAT SERVER =========================
# =====================================================

class ChatServer:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.clients = {}          # {socket: username}
        self.user_sockets = {}     # {username: socket}
        self.users = load_users()
        self.lock = threading.Lock()

    def start(self):
        self.server.bind((self.host, self.port))
        self.server.listen()
        print(f"[SERVER] Chạy trên {self.host}:{self.port}")

        while True:
            sock, addr = self.server.accept()
            print(f"[NEW] {addr} đã kết nối")
            threading.Thread(target=self.handle_client, args=(sock,), daemon=True).start()

    # =====================================================
    # ================  HANDLE CLIENT  ====================
    # =====================================================

    def handle_client(self, client_socket):
        username = None
        try:
            # Lấy gói đầu tiên
            first = next(iter_json_packets(client_socket), None)
            if not first:
                client_socket.close()
                return

            # ========== REGISTER ==========
            if first.get("type") == "register":
                username = first.get("username", "").strip()
                password = first.get("password", "")
                ok, msg = self.handle_register(username, password)
                send_json(client_socket, {"type": "register_result", "ok": ok, "message": msg})
                if not ok:
                    client_socket.close()
                    return

                # Chờ gói login tiếp theo
                first = next(iter_json_packets(client_socket), None)
                if not first:
                    client_socket.close()
                    return

            # ========== LOGIN ==========
            if first.get("type") != "login":
                send_json(client_socket, {"type": "login_result", "ok": False, "message": "Thiếu gói login"})
                client_socket.close()
                return

            username = first.get("username", "").strip()
            password = first.get("password", "")
            ok, msg = self.handle_login(username, password)
            send_json(client_socket, {"type": "login_result", "ok": ok, "message": msg})

            # ❗ IF LOGIN FAIL → NGẮT LUÔN
            if not ok:
                client_socket.close()
                return

            # ĐĂNG NHẬP THÀNH CÔNG
            with self.lock:
                self.clients[client_socket] = username
                self.user_sockets[username] = client_socket

            self.broadcast_system(f"[{username}] đã tham gia phòng chat!")
            self.send_presence()

            # ========== NHẬN TỪ CLIENT ==========
            for packet in iter_json_packets(client_socket):
                ptype = packet.get("type")

                # ----- chat công khai -----
                if ptype == "chat":
                    text = packet.get("text", "").strip()
                    if text:
                        ts = datetime.now().strftime("%H:%M:%S")
                        self.broadcast({
                            "type": "chat",
                            "from": username,
                            "text": text,
                            "ts": ts
                        })

                # ----- DM (tin nhắn riêng) -----
                elif ptype == "dm":
                    to_user = packet.get("to", "").strip()
                    text = packet.get("text", "").strip()

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
                    send_json(client_socket, {"type": "system", "text": f"Gói không hỗ trợ: {ptype}"})

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
            except:
                pass

            if uname:
                self.broadcast_system(f"[{uname}] đã rời khỏi phòng chat!")
                self.send_presence()

    # =====================================================
    # ================== AUTH HELPERS =====================
    # =====================================================

    def handle_register(self, username, password):
        if not username or not password:
            return False, "Thiếu username/password"

        with self.lock:
            if username in self.users:
                return False, "Tên đã tồn tại"

            # Lưu BCRYPT HASH, không lưu plaintext nữa
            self.users[username] = hash_password(password)
            save_users(self.users)

        print(f"[REGISTER] {username} đã đăng ký")
        return True, "Đăng ký thành công"

    def handle_login(self, username, password):
        stored = self.users.get(username)
        if stored is None:
            return False, "Sai tài khoản hoặc mật khẩu"

        ok = False

        if isinstance(stored, str):
            if looks_like_bcrypt(stored):
                # TH đã hash bằng bcrypt
                ok = check_password(password, stored)
            else:
                # TH còn plaintext (rất ít sau migrate)
                ok = (stored == password)
                if ok:
                    # Nâng cấp luôn user này lên bcrypt
                    with self.lock:
                        self.users[username] = hash_password(password)
                        save_users(self.users)
        else:
            ok = False

        if not ok:
            return False, "Sai tài khoản hoặc mật khẩu"

        # ❗CHẶN LOGIN TRÙNG
        with self.lock:
            if username in self.user_sockets:
                return False, "Tài khoản đang đăng nhập ở nơi khác"

        return True, "Đăng nhập thành công"

    # =====================================================
    # ================== BROADCAST / DM ===================
    # =====================================================

    def broadcast(self, message, exclude=None):
        with self.lock:
            targets = list(self.clients.items())

        for sock, uname in targets:
            if exclude and uname == exclude:
                continue
            send_json(sock, message)

    def broadcast_system(self, text, exclude=None):
        self.broadcast({"type": "system", "text": text}, exclude)

    def send_presence(self):
        with self.lock:
            online = list(self.user_sockets.keys())
        self.broadcast({"type": "presence", "users": online})

    def send_dm(self, from_user, to_user, obj):
        with self.lock:
            to_sock = self.user_sockets.get(to_user)
            from_sock = self.user_sockets.get(from_user)

        if to_sock:
            send_json(to_sock, obj)
        if from_sock:
            send_json(from_sock, obj)


if __name__ == "__main__":
    print("=" * 50)
    print("CHAT SERVER (register/login + chat + dm + presence)")
    print("=" * 50)
    ChatServer().start()
