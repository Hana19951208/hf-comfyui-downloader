import unittest

from hf_client import HuggingFaceRepositoryClient
from hf_utils import RepoRef


class FakeApi:
    def __init__(self, entries):
        self.entries = entries
        self.calls = []

    def list_repo_tree(self, **kwargs):
        self.calls.append(kwargs)
        return self.entries


class FileEntry:
    def __init__(self, path, size=0):
        self.path = path
        self.size = size


class DirectoryEntry:
    def __init__(self, path):
        self.path = path


class HuggingFaceRepositoryClientTests(unittest.TestCase):
    def test_list_files_filters_out_directories(self) -> None:
        api = FakeApi(
            [
                FileEntry("README.md", 12),
                FileEntry("models/a.safetensors", 2048),
                DirectoryEntry("models"),
            ]
        )
        client = HuggingFaceRepositoryClient(api=api)

        files = client.list_files(
            RepoRef(repo_id="tewea/demo", repo_type="model", revision="main")
        )

        self.assertEqual([file.path for file in files], ["README.md", "models/a.safetensors"])
        self.assertEqual(files[1].size, 2048)
        self.assertEqual(api.calls[0]["repo_id"], "tewea/demo")
        self.assertEqual(api.calls[0]["repo_type"], "model")
        self.assertEqual(api.calls[0]["revision"], "main")


if __name__ == "__main__":
    unittest.main()
