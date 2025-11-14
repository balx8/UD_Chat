# ui_chat.py
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from tag_color import setup_chat_tags
from enter_send import bind_enter_to_send


def build_chat_ui(app):
    """
    app: instance của ChatClientApp
    """

    # Frame chat chính
    app.chat_frame = tk.Frame(app.root, padx=10, pady=10)
    app.chat_frame.pack(fill="both", expand=True)

    header = tk.Label(
        app.chat_frame,
        text=f"💬 Phòng Chat - Xin chào {app.username}!",
        font=("Segoe UI", 12, "bold")
    )
    header.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

    # Khung tin nhắn
    tk.Label(app.chat_frame, text="Tin nhắn:").grid(row=1, column=0, sticky="w")
    app.chat_window = ScrolledText(
        app.chat_frame, height=18, width=80,
        state="disabled", wrap="word"
    )
    app.chat_window.grid(row=2, column=0, columnspan=2,
                         sticky="nsew", padx=(0, 8))

    # Danh sách người online
    tk.Label(app.chat_frame, text="👥 Online:").grid(row=1, column=2, sticky="w")
    app.users_list = tk.Listbox(app.chat_frame, height=18, width=24)
    app.users_list.grid(row=2, column=2, sticky="ns")

    # Ô nhập tin nhắn
    app.message_entry = tk.Entry(app.chat_frame)
    app.message_entry.grid(row=3, column=0, sticky="ew", pady=(8, 0))

    app.pm_label = tk.Label(app.chat_frame, text="Chế độ: Công khai", fg="#555")
    app.pm_label.grid(row=3, column=1, sticky="w", padx=(8, 0))

    # Nút gửi
    app.send_button = tk.Button(
        app.chat_frame, text="Gửi", width=10, command=app.send_message
    )
    app.send_button.grid(row=3, column=2, sticky="e", pady=(8, 0))

    # Layout
    app.chat_frame.rowconfigure(2, weight=1)
    app.chat_frame.columnconfigure(0, weight=1)

    # Tag màu
    setup_chat_tags(app.chat_window)

    # Enter để gửi tin nhắn
    bind_enter_to_send(app.message_entry, app.send_message)
