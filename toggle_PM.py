import tkinter as tk

def toggle_pm_target(self, event=None):
    try:
            index = self.users_list.curselection()
            if not index:
                return
            sel = self.users_list.get(index[0])
        except:
            return

        if sel == self.username:
            self.pm_target = None
            self.pm_label.config(text="Chế độ: Công khai", fg="#555")
            return

        if self.pm_target == sel:
            self.pm_target = None
            self.pm_label.config(text="Chế độ: Công khai", fg="#555")
        else:
            self.pm_target = sel
            self.pm_label.config(text=f"Chế độ: Riêng → {sel}", fg="#6a1b9a")
