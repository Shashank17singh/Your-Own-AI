__all__ = ["Dialog"]
from tkinter import Frame


class Dialog:
    command = None

    def __init__(self, master=None, **options):
        if not master:
            master = options.get("parent")
        self.master = master
        self.options = options

    def _fixoptions(self):
        pass  # hook

    def _fixresult(self, widget, result):
        return result  # hook

    def show(self, **options):
        for k, v in options.items():
            self.options[k] = v
        self._fixoptions()
        w = Frame(self.master)
        try:
            s = w.tk.call(self.command, *w._options(self.options))
            s = self._fixresult(w, s)
        finally:
            try:
                w.destroy()
            except:
                pass
        return s
