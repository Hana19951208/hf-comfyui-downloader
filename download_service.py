from __future__ import annotations

import subprocess
from collections.abc import Callable

from hf_utils import (
    DEFAULT_HF_ENDPOINT,
    DownloadRequest,
    build_hf_download_command,
    build_runtime_env,
)


LogCallback = Callable[[str], None]


class DownloadService:
    def run_download(
        self,
        request: DownloadRequest,
        on_log: LogCallback | None = None,
        endpoint: str | None = None,
        proxy_strategy: str = "mirror_direct_xethub_proxy",
    ) -> int:
        command = build_hf_download_command(request)
        if on_log:
            on_log("执行命令: " + self._format_command(command))
            on_log(f"下载端点: {endpoint or DEFAULT_HF_ENDPOINT}")
            on_log(f"代理策略: {proxy_strategy}")

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=build_runtime_env(endpoint, proxy_strategy),
        )

        if process.stdout is not None:
            for line in process.stdout:
                if on_log:
                    on_log(line.rstrip())

        return process.wait()

    @staticmethod
    def _format_command(command: list[str]) -> str:
        masked: list[str] = []
        for index, value in enumerate(command):
            if index > 0 and command[index - 1] == "--token":
                masked.append("***")
            else:
                masked.append(value)
        return subprocess.list2cmdline(masked)
