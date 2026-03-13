from __future__ import annotations

import os
import shutil
import threading
import time
from tkinter import Button, Entry, Frame, Label, StringVar, Text, filedialog, messagebox
import tkinter as tk
from tkinter import ttk

from download_service import DownloadService
from hf_client import HuggingFaceRepositoryClient
from hf_utils import (
    DEFAULT_HF_ENDPOINT,
    DownloadRequest,
    RepoFile,
    RepoRef,
    format_size,
    get_download_progress_bytes,
    list_model_subdirectories,
    parse_huggingface_url,
    resolve_hf_endpoint,
    resolve_local_file_path,
)


DEFAULT_COMFYUI_DIR = r"D:\ComfyUI\models"


class DownloaderApp(Frame):
    def __init__(
        self,
        master: tk.Misc,
        client: HuggingFaceRepositoryClient | None = None,
        downloader: DownloadService | None = None,
    ) -> None:
        super().__init__(master)
        self.master = master
        self.client = client or HuggingFaceRepositoryClient()
        self.downloader = downloader or DownloadService()
        self.current_repo: RepoRef | None = None
        self.files: list[RepoFile] = []

        self.url_var = StringVar()
        self.target_dir_var = StringVar(value=DEFAULT_COMFYUI_DIR)
        self.repo_info_var = StringVar(value="尚未加载仓库")
        self.status_var = StringVar(value="就绪")
        self.progress_var = StringVar(value="进度: -")
        self.speed_var = StringVar(value="速度: -")
        self.eta_var = StringVar(value="剩余时间: -")
        self.quick_dir_var = StringVar(value="选择常用目录")
        self.available_model_dirs: list[str] = []
        self.download_in_progress = False
        self.current_endpoint = DEFAULT_HF_ENDPOINT

        self._build_layout()
        self._check_environment()
        self.refresh_model_dirs()

    def _build_layout(self) -> None:
        self.master.title("HF ComfyUI Downloader")
        self.master.geometry("1180x760")
        self.master.minsize(980, 640)
        self.pack(fill="both", expand=True, padx=12, pady=12)

        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=4)
        self.rowconfigure(1, weight=1)

        top_bar = Frame(self)
        top_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        top_bar.columnconfigure(1, weight=1)

        Label(top_bar, text="Hugging Face 地址:").grid(row=0, column=0, sticky="w")
        url_entry = Entry(top_bar, textvariable=self.url_var, font=("Consolas", 12))
        url_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        Button(top_bar, text="读取文件", command=self.load_files).grid(row=0, column=2, padx=(0, 8))
        Button(top_bar, text="清空", command=self.clear_form).grid(row=0, column=3)

        left_panel = Frame(self, relief="groove", borderwidth=1)
        left_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left_panel.columnconfigure(1, weight=1)
        left_panel.rowconfigure(5, weight=1)

        Label(left_panel, text="目标目录:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        Entry(left_panel, textvariable=self.target_dir_var, font=("Consolas", 11)).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=(10, 6)
        )
        Button(left_panel, text="浏览...", command=self.choose_target_dir).grid(
            row=0, column=2, sticky="e", padx=(0, 10), pady=(10, 6)
        )

        Label(left_panel, text="常用目录:").grid(row=1, column=0, sticky="w", padx=10, pady=6)
        self.quick_dir_box = ttk.Combobox(
            left_panel,
            textvariable=self.quick_dir_var,
            values=[],
            state="readonly",
            height=12,
        )
        self.quick_dir_box.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=6)
        self.quick_dir_box.bind("<<ComboboxSelected>>", self.apply_quick_dir)
        Button(left_panel, text="刷新目录", command=self.refresh_model_dirs).grid(
            row=1, column=2, sticky="e", padx=(0, 10), pady=6
        )

        Label(left_panel, text="仓库信息:").grid(row=2, column=0, sticky="nw", padx=10, pady=6)
        Label(
            left_panel,
            textvariable=self.repo_info_var,
            justify="left",
            anchor="w",
            wraplength=420,
        ).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 10), pady=6)

        Label(left_panel, text="文件列表:").grid(row=3, column=0, sticky="w", padx=10, pady=6)
        self.file_tree = ttk.Treeview(left_panel, columns=("size",), show="tree headings", selectmode="browse")
        self.file_tree.heading("#0", text="文件路径")
        self.file_tree.heading("size", text="大小")
        self.file_tree.column("#0", width=360, stretch=True)
        self.file_tree.column("size", width=110, anchor="e", stretch=False)
        self.file_tree.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
        left_panel.rowconfigure(4, weight=1)

        action_bar = Frame(left_panel)
        action_bar.grid(row=5, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        action_bar.columnconfigure(0, weight=1)
        Button(action_bar, text="下载选中文件", command=self.download_selected).grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        Button(action_bar, text="打开目标目录", command=self.open_target_dir).grid(row=0, column=1, sticky="ew")

        right_panel = Frame(self, relief="groove", borderwidth=1)
        right_panel.grid(row=1, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        Label(right_panel, text="运行日志:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))
        self.log_text = Text(right_panel, font=("Consolas", 11), wrap="word")
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        bottom_bar = Frame(right_panel)
        bottom_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_bar.columnconfigure(0, weight=1)
        Label(bottom_bar, textvariable=self.status_var, anchor="w").grid(row=0, column=0, sticky="w")
        Label(bottom_bar, textvariable=self.progress_var, anchor="w").grid(row=0, column=1, sticky="w", padx=(12, 0))
        Label(bottom_bar, textvariable=self.speed_var, anchor="w").grid(row=0, column=2, sticky="w", padx=(12, 0))
        Label(bottom_bar, textvariable=self.eta_var, anchor="w").grid(row=0, column=3, sticky="w", padx=(12, 0))
        Button(bottom_bar, text="清空日志", command=self.clear_logs).grid(row=0, column=4, padx=(12, 0))

        self.progress_bar = ttk.Progressbar(right_panel, orient="horizontal", mode="determinate", maximum=100)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _check_environment(self) -> None:
        if shutil.which("hf") is None:
            self.append_log("未找到 hf 命令，请先安装 huggingface_hub CLI。")
            messagebox.showwarning("环境缺失", "未找到 hf 命令，请先确认命令行中可以执行 hf。")
        if not os.environ.get("HF_TOKEN"):
            self.append_log("未检测到 HF_TOKEN，公开仓库仍可用，私有仓库会失败。")

    def clear_form(self) -> None:
        self.url_var.set("")
        self.repo_info_var.set("尚未加载仓库")
        self.status_var.set("就绪")
        self.files = []
        self.current_repo = None
        self.quick_dir_var.set("选择常用目录")
        for item_id in self.file_tree.get_children():
            self.file_tree.delete(item_id)

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", "end")

    def choose_target_dir(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.target_dir_var.get() or DEFAULT_COMFYUI_DIR)
        if selected:
            self.target_dir_var.set(selected)
            self._sync_quick_dir_with_target()

    def reset_target_dir(self) -> None:
        self.target_dir_var.set(DEFAULT_COMFYUI_DIR)
        self.refresh_model_dirs()

    def apply_quick_dir(self, _event: object | None = None) -> None:
        selected = self.quick_dir_var.get()
        if not selected or selected == "选择常用目录":
            return
        self.target_dir_var.set(os.path.join(DEFAULT_COMFYUI_DIR, selected))

    def refresh_model_dirs(self) -> None:
        self.available_model_dirs = list_model_subdirectories(DEFAULT_COMFYUI_DIR)
        values = ["选择常用目录", *self.available_model_dirs]
        self.quick_dir_box["values"] = values
        self._sync_quick_dir_with_target()
        if self.available_model_dirs:
            self.append_log(f"已读取模型目录，共 {len(self.available_model_dirs)} 个子目录。")
        else:
            self.append_log("未在 ComfyUI 模型目录下找到子文件夹。")

    def _sync_quick_dir_with_target(self) -> None:
        target_dir = self.target_dir_var.get().strip()
        normalized_root = os.path.normpath(DEFAULT_COMFYUI_DIR)
        normalized_target = os.path.normpath(target_dir) if target_dir else ""
        parent_dir = os.path.dirname(normalized_target)
        if parent_dir == normalized_root:
            directory_name = os.path.basename(normalized_target)
            if directory_name in self.available_model_dirs:
                self.quick_dir_var.set(directory_name)
                return
        self.quick_dir_var.set("选择常用目录")

    def load_files(self) -> None:
        raw_url = self.url_var.get().strip()
        if not raw_url:
            messagebox.showerror("缺少地址", "请先输入 Hugging Face 页面地址。")
            return

        self.status_var.set("正在读取仓库文件...")
        self.append_log(f"开始解析地址: {raw_url}")
        threading.Thread(target=self._load_files_worker, args=(raw_url,), daemon=True).start()

    def _load_files_worker(self, raw_url: str) -> None:
        try:
            endpoint = resolve_hf_endpoint(raw_url)
            repo = parse_huggingface_url(raw_url)
            files = HuggingFaceRepositoryClient(endpoint=endpoint).list_files(repo)
            self.after(0, lambda: self._apply_loaded_files(repo, files, endpoint))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._handle_error("读取失败", exc))

    def _apply_loaded_files(self, repo: RepoRef, files: list[RepoFile], endpoint: str) -> None:
        self.current_repo = repo
        self.files = files
        self.current_endpoint = endpoint
        self.repo_info_var.set(
            f"仓库: {repo.repo_id}\n类型: {repo.repo_type}\n分支/版本: {repo.revision}\n端点: {endpoint}\n文件数: {len(files)}"
        )

        for item_id in self.file_tree.get_children():
            self.file_tree.delete(item_id)
        for file in files:
            self.file_tree.insert("", "end", iid=file.path, text=file.path, values=(format_size(file.size),))

        self.status_var.set(f"已加载 {len(files)} 个文件")
        self.append_log(f"读取完成: {repo.repo_id}，共 {len(files)} 个文件。")
        self.append_log(f"解析端点: {endpoint}")

    def download_selected(self) -> None:
        if self.current_repo is None:
            messagebox.showerror("尚未加载", "请先读取仓库文件列表。")
            return

        selected_items = self.file_tree.selection()
        if not selected_items:
            messagebox.showerror("未选择文件", "请先在文件列表中选择一个文件。")
            return

        target_dir = self.target_dir_var.get().strip()
        if not target_dir:
            messagebox.showerror("缺少目录", "请先选择下载目录。")
            return

        os.makedirs(target_dir, exist_ok=True)
        filename = selected_items[0]
        nested_parent = os.path.dirname(resolve_local_file_path(target_dir, filename))
        os.makedirs(nested_parent, exist_ok=True)
        expected_size = next((item.size for item in self.files if item.path == filename), 0)
        request = DownloadRequest(
            repo_id=self.current_repo.repo_id,
            repo_type=self.current_repo.repo_type,
            revision=self.current_repo.revision,
            filename=filename,
            target_dir=target_dir,
        )
        current_size, _ = get_download_progress_bytes(target_dir, filename)
        self.download_in_progress = True
        self.progress_bar.configure(value=0)
        self.progress_var.set(progress_text(current_size, expected_size))
        self.speed_var.set("速度: 0 B/s")
        self.eta_var.set(eta_text(current_size, expected_size, 0))
        self.status_var.set(f"正在下载: {filename}")
        if current_size > 0:
            self.append_log(f"检测到未完成下载，继续续传: {format_size(current_size)}")
        self.append_log(f"准备下载: {filename}")
        threading.Thread(
            target=self._download_worker,
            args=(request, expected_size, self.current_endpoint),
            daemon=True,
        ).start()

    def _download_worker(
        self,
        request: DownloadRequest,
        expected_size: int,
        endpoint: str,
    ) -> None:
        progress_thread = threading.Thread(
            target=self._track_download_progress,
            args=(request.target_dir, request.filename, expected_size),
            daemon=True,
        )
        progress_thread.start()
        try:
            exit_code = self.downloader.run_download(request, on_log=self._thread_safe_log, endpoint=endpoint)
            if exit_code != 0:
                raise RuntimeError(f"hf download 执行失败，退出码: {exit_code}")
            self.after(0, lambda: self._finish_download(request.filename, request.target_dir))
        except Exception as exc:  # noqa: BLE001
            self.after(0, lambda: self._handle_error("下载失败", exc))
        finally:
            self.download_in_progress = False

    def _finish_download(self, filename: str, target_dir: str) -> None:
        self.status_var.set("下载完成")
        self.progress_bar.configure(value=100)
        self.progress_var.set("进度: 100.0%")
        self.speed_var.set("速度: 0 B/s")
        self.eta_var.set("剩余时间: 0秒")
        self.append_log(f"下载完成: {filename} -> {target_dir}")
        messagebox.showinfo("下载完成", f"文件已下载到:\n{target_dir}")

    def _handle_error(self, title: str, exc: Exception) -> None:
        self.status_var.set(title)
        self.append_log(f"{title}: {exc}")
        messagebox.showerror(title, str(exc))

    def _thread_safe_log(self, message: str) -> None:
        self.after(0, lambda: self.append_log(message))

    def append_log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def open_target_dir(self) -> None:
        target_dir = self.target_dir_var.get().strip()
        if not target_dir:
            messagebox.showerror("缺少目录", "当前没有可打开的目录。")
            return

        os.makedirs(target_dir, exist_ok=True)
        os.startfile(target_dir)

    def _track_download_progress(self, target_dir: str, filename: str, expected_size: int) -> None:
        last_size, _ = get_download_progress_bytes(target_dir, filename)
        last_time = time.time()
        while self.download_in_progress:
            current_size, _ = get_download_progress_bytes(target_dir, filename)
            now = time.time()
            elapsed = max(now - last_time, 0.001)
            speed = max(current_size - last_size, 0) / elapsed
            last_size = current_size
            last_time = now
            self.after(0, lambda cs=current_size, es=expected_size, sp=speed: self._update_progress(cs, es, sp))
            time.sleep(0.5)

        final_size, _ = get_download_progress_bytes(target_dir, filename)
        self.after(0, lambda: self._update_progress(final_size, expected_size, 0))

    def _update_progress(self, current_size: int, expected_size: int, speed: float) -> None:
        percent = 0.0
        if expected_size > 0:
            percent = min((current_size / expected_size) * 100, 100.0)
        self.progress_bar.configure(value=percent)
        self.progress_var.set(progress_text(current_size, expected_size))
        self.speed_var.set(f"速度: {format_size(int(speed))}/s")
        self.eta_var.set(eta_text(current_size, expected_size, speed))


def progress_text(current_size: int, expected_size: int) -> str:
    if expected_size <= 0:
        return f"进度: 已下载 {format_size(current_size)}"
    percent = min((current_size / expected_size) * 100, 100.0)
    return f"进度: {percent:.1f}% ({format_size(current_size)} / {format_size(expected_size)})"


def eta_text(current_size: int, expected_size: int, speed: float) -> str:
    if expected_size <= 0 or speed <= 0:
        return "剩余时间: -"

    remaining_seconds = max(int((expected_size - current_size) / speed), 0)
    if remaining_seconds < 60:
        return f"剩余时间: {remaining_seconds}秒"
    minutes, seconds = divmod(remaining_seconds, 60)
    if minutes < 60:
        return f"剩余时间: {minutes}分{seconds}秒"
    hours, minutes = divmod(minutes, 60)
    return f"剩余时间: {hours}小时{minutes}分"
