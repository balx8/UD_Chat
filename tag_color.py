# tag_color.py

def setup_chat_tags(chat_window):
    chat_window.configure(font=("Segoe UI", 10))

    chat_window.tag_config(
        "me", foreground="#1b76d1", font=("Segoe UI", 10, "bold"))

    chat_window.tag_config(
        "pm_me", foreground="#6a1b9a", font=("Segoe UI", 10, "bold"))

    chat_window.tag_config(
        "pm_in", foreground="#2e7d32", font=("Segoe UI", 10, "bold"))

    chat_window.tag_config(
        "sys", foreground="#888888", font=("Segoe UI", 9, "italic"))
