import socket
import threading
import json
from datetime import datetime
from pathlib import Path

USERS_FILE = Path("users.json")
def load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    users = {"admin": "admin123", "user1": "pass1", "user2": "pass2"}
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    return users

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

def send_json(sock, obj):
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    sock.sendall(data)

def iter_json_packets(sock):
    """Đọc từng dòng JSON từ socket (có bắt lỗi)."""
    with sock.makefile("r", encoding="utf-8", newline="\n") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield {"type": "system", "text": f"JSON không hợp lệ: {line[:50]}..."}
class ChatServer:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.clients = {}          
        self.user_sockets = {}     
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
    def handle_client(self, client_socket):
        username = None
        try:
            first = next(iter_json_packets(client_socket), None)
            if not first:
                client_socket.close()
                return

            # REGISTER
            if first.get("type") == "register":
                username = first.get("username", "").strip()
                password = first.get("password", "")
                ok, msg = self.handle_register(username, password)
                send_json(client_socket, {"type": "register_result", "ok": ok, "message": msg})
                if not ok:
                    client_socket.close()
                    return

                first = next(iter_json_packets(client_socket), None)
                if not first:
                    client_socket.close()
                    return

            # LOGIN
            if first.get("type") != "login":
                send_json(client_socket, {"type": "login_result", "ok": False, "message": "Thiếu gói login"})
                client_socket.close()
                return

            username = first.get("username", "").strip()
            password = first.get("password", "")
            ok, msg = self.handle_login(username, password)
            send_json(client_socket, {"type": "login_result", "ok": ok, "message": msg})
            if not ok:
                client_socket.close()
                return

            # ĐĂNG NHẬP THÀNH CÔNG
            with self.lock:
                self.clients[client_socket] = username
                self.user_sockets[username] = client_socket

            self.broadcast_system(f"[{username}] đã tham gia phòng chat!")
            self.send_presence()

            # NHẬN TIN
            for packet in iter_json_packets(client_socket):
                ptype = packet.get("type")

                if ptype == "chat":
                    text = str(packet.get("text", "")).strip()
                    if text:
                        ts = datetime.now().strftime("%H:%M:%S")
                        self.broadcast({
                            "type": "chat",
                            "from": username,
                            "text": text,
                            "ts": ts
                        })

                elif ptype == "dm":
                    to_user = packet.get("to", "").strip()
                    text = packet.get("text", "").strip()
                    if to_user and text:
                        ts = datetime.now().strftime("%H:%M:%S")
                        self.send_dm(
                            from_user=username,
                            to_user=to_user,
                            obj={
                                "type": "dm",
                                "from": username,
                                "to": to_user,
                                "text": text,
                                "ts": ts
                            }
                        )

                elif ptype == "quit":
                    break

                else:
                    send_json(client_socket, {"type": "system", "text": f"Loại gói không hỗ trợ: {ptype}"})

        except Exception as e:
            print(f"[ERROR] {e}")

        finally:
            with self.lock:
                if client_socket in self.clients:
                    uname = self.clients.pop(client_socket)
                    self.user_sockets.pop(uname, None)
                else:
                    uname = username

            try: client_socket.close()
            except: pass

            if uname:
                self.broadcast_system(f"[{uname}] đã rời khỏi phòng chat!")
                self.send_presence()
    def handle_register(self, username, password):
        if not username or not password:
            return False, "Thiếu username/password"

        with self.lock:
            if username in self.users:
                return False, "Tên đã tồn tại"

            self.users[username] = password
            save_users(self.users)

        print(f"[REGISTER] {username} đã đăng ký")
        return True, "Đăng ký thành công"

    def handle_login(self, username, password):
        if username not in self.users or self.users[username] != password:
            return False, "Sai tài khoản hoặc mật khẩu"
        with self.lock:
            if username in self.user_sockets:
                return False, "Tài khoản đang đăng nhập ở nơi khác"
        return True, "Đăng nhập thành công"

    # =====================================================
    # =============== BROADCAST + PRESENCE ===============
    # =====================================================

    def broadcast(self, message, exclude=None):
        with self.lock:
            targets = list(self.clients.items())

        for sock, uname in targets:
            if exclude and uname == exclude:
                continue
            try:
                send_json(sock, message)
            except:
                pass

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
            try: send_json(to_sock, obj)
            except: pass

        if from_sock:
            try: send_json(from_sock, obj)
            except: pass


# =====================================================
# ================== MAIN =============================
# =====================================================

if __name__ == "__main__":
    print("=" * 50)
    print("CHAT SERVER (register/login + chat + dm + presence)")
    print("=" * 50)
    ChatServer().start()
