# enter_send.py

def bind_enter_to_send(entry_widget, send_callback):
    """
    Gán phím Enter để gửi tin nhắn
    """
    entry_widget.bind("<Return>", lambda e: send_callback())
