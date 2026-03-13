from __future__ import annotations

import tkinter as tk

from app import DownloaderApp


def main() -> None:
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
