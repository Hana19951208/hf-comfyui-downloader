from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from huggingface_hub._local_folder import _short_hash, get_local_download_paths


DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"
DEFAULT_PROXY_STRATEGY = "mirror_direct_xethub_proxy"
HUGGINGFACE_HOSTS = {"huggingface.co", "www.huggingface.co", "hf-mirror.com", "www.hf-mirror.com"}
PROXY_STRATEGIES = [
    {"id": "mirror_direct_xethub_proxy", "label": "镜像直连，xethub 走代理"},
    {"id": "all_direct", "label": "全部直连"},
    {"id": "all_proxy", "label": "全部走代理"},
]


@dataclass(frozen=True)
class RepoRef:
    repo_id: str
    repo_type: str = "model"
    revision: str = "main"


@dataclass(frozen=True)
class RepoFile:
    path: str
    size: int = 0


@dataclass(frozen=True)
class DownloadRequest:
    repo_id: str
    filename: str
    target_dir: str
    repo_type: str = "model"
    revision: str | None = None
    token: str | None = None


def normalize_huggingface_url(url: str) -> str:
    repo = parse_huggingface_url(url)
    endpoint = resolve_hf_endpoint(url)
    base_url = f"{endpoint}/{repo.repo_id}"
    if repo.repo_type == "dataset":
        base_url = f"{endpoint}/datasets/{repo.repo_id}"
    elif repo.repo_type == "space":
        base_url = f"{endpoint}/spaces/{repo.repo_id}"
    return f"{base_url}/tree/{repo.revision}"


def parse_huggingface_url(url: str) -> RepoRef:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc not in HUGGINGFACE_HOSTS:
        raise ValueError("只支持 huggingface.co 或 hf-mirror.com 地址。")

    parts = [segment for segment in parsed.path.split("/") if segment]
    if len(parts) < 2:
        raise ValueError("无法从地址中识别仓库。")

    repo_type = "model"
    start_index = 0
    if parts[0] in {"datasets", "spaces"}:
        repo_type = "dataset" if parts[0] == "datasets" else "space"
        start_index = 1

    if len(parts) < start_index + 2:
        raise ValueError("仓库地址不完整。")

    owner = parts[start_index]
    repo_name = parts[start_index + 1]
    repo_id = f"{owner}/{repo_name}"

    revision = "main"
    if len(parts) > start_index + 2:
        marker = parts[start_index + 2]
        remainder = parts[start_index + 3 :]
        if marker == "tree":
            revision = "/".join(remainder) or "main"
        elif marker == "blob":
            if not remainder:
                revision = "main"
            else:
                revision = "/".join(remainder[:-1]) or "main"

    return RepoRef(repo_id=repo_id, repo_type=repo_type, revision=revision)


def build_hf_download_command(request: DownloadRequest) -> list[str]:
    command = [
        "hf",
        "download",
        request.repo_id,
        request.filename,
        "--repo-type",
        request.repo_type,
    ]
    if request.revision:
        command.extend(["--revision", request.revision])
    command.extend(["--local-dir", request.target_dir])

    token = request.token or os.environ.get("HF_TOKEN")
    if token:
        command.extend(["--token", token])
    return command


def resolve_hf_endpoint(url: str | None = None) -> str:
    if not url:
        return DEFAULT_HF_ENDPOINT

    parsed = urlparse(url.strip())
    if "hf-mirror.com" in parsed.netloc:
        return DEFAULT_HF_ENDPOINT
    return DEFAULT_HF_ENDPOINT


def build_runtime_env(endpoint: str | None = None, proxy_strategy: str = DEFAULT_PROXY_STRATEGY) -> dict[str, str]:
    env = dict(os.environ)
    env["HF_ENDPOINT"] = endpoint or DEFAULT_HF_ENDPOINT

    managed_hosts = [
        "hf-mirror.com",
        ".hf-mirror.com",
        "huggingface.co",
        ".huggingface.co",
        "xethub.hf.co",
        ".xethub.hf.co",
        "cas-bridge.xethub.hf.co",
    ]
    no_proxy_hosts = no_proxy_hosts_for_strategy(proxy_strategy)
    current_no_proxy = env.get("NO_PROXY", "")
    current_entries = [entry.strip() for entry in current_no_proxy.split(",") if entry.strip()]
    current_entries = [entry for entry in current_entries if entry not in managed_hosts]
    for host in no_proxy_hosts:
        if host not in current_entries:
            current_entries.append(host)
    env["NO_PROXY"] = ",".join(current_entries)
    return env


def no_proxy_hosts_for_strategy(proxy_strategy: str) -> list[str]:
    mirror_hosts = [
        "hf-mirror.com",
        ".hf-mirror.com",
        "huggingface.co",
        ".huggingface.co",
    ]
    xet_hosts = [
        "xethub.hf.co",
        ".xethub.hf.co",
        "cas-bridge.xethub.hf.co",
    ]

    if proxy_strategy == "all_direct":
        return [*mirror_hosts, *xet_hosts]
    if proxy_strategy == "all_proxy":
        return []
    return mirror_hosts


def list_model_subdirectories(root_dir: str) -> list[str]:
    if not root_dir or not os.path.isdir(root_dir):
        return []

    directory_names = [
        entry.name
        for entry in os.scandir(root_dir)
        if entry.is_dir()
    ]
    return sorted(directory_names, key=str.lower)


def resolve_local_file_path(target_dir: str, filename: str) -> str:
    parts = [segment for segment in filename.replace("\\", "/").split("/") if segment]
    return os.path.join(target_dir, *parts)


def get_download_progress_bytes(target_dir: str, filename: str) -> tuple[int, str | None]:
    download_paths = get_local_download_paths(Path(target_dir), filename)
    prefix = _short_hash(download_paths.metadata_path.name)
    candidates = sorted(
        download_paths.metadata_path.parent.glob(f"{prefix}.*.incomplete"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.stat().st_size, str(candidate)

    if download_paths.file_path.exists():
        return download_paths.file_path.stat().st_size, str(download_paths.file_path)

    return 0, None


def format_size(size: int) -> str:
    if size <= 0:
        return "-"

    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"
