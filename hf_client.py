from __future__ import annotations

from huggingface_hub import HfApi

from hf_utils import RepoFile, RepoRef


class HuggingFaceRepositoryClient:
    def __init__(self, api: HfApi | None = None, endpoint: str | None = None) -> None:
        self._api = api or HfApi(token=None, endpoint=endpoint)

    def list_files(self, repo: RepoRef) -> list[RepoFile]:
        entries = self._api.list_repo_tree(
            repo_id=repo.repo_id,
            repo_type=repo.repo_type,
            revision=repo.revision,
            recursive=False,
            expand=False,
        )
        files: list[RepoFile] = []
        for entry in entries:
            entry_type = entry.__class__.__name__.lower()
            if "directory" in entry_type or "folder" in entry_type:
                continue
            path = getattr(entry, "path", "")
            if not path:
                continue
            files.append(RepoFile(path=path, size=int(getattr(entry, "size", 0) or 0)))
        return files
