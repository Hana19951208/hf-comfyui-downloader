import tempfile
import unittest
from pathlib import Path

from hf_utils import (
    DEFAULT_PROXY_STRATEGY,
    DownloadRequest,
    DEFAULT_HF_ENDPOINT,
    PROXY_STRATEGIES,
    build_hf_download_command,
    build_runtime_env,
    format_size,
    get_download_progress_bytes,
    list_model_subdirectories,
    normalize_huggingface_url,
    parse_huggingface_url,
    resolve_local_file_path,
    resolve_hf_endpoint,
)


class ParseHuggingFaceUrlTests(unittest.TestCase):
    def test_parse_tree_url(self) -> None:
        parsed = parse_huggingface_url(
            "https://huggingface.co/tewea/z_image_turbo_bf16_nsfw/tree/main"
        )

        self.assertEqual(parsed.repo_id, "tewea/z_image_turbo_bf16_nsfw")
        self.assertEqual(parsed.repo_type, "model")
        self.assertEqual(parsed.revision, "main")

    def test_parse_blob_url_with_nested_revision(self) -> None:
        parsed = parse_huggingface_url(
            "https://huggingface.co/datasets/acme/demo/blob/feature/test/data.json"
        )

        self.assertEqual(parsed.repo_id, "acme/demo")
        self.assertEqual(parsed.repo_type, "dataset")
        self.assertEqual(parsed.revision, "feature/test")

    def test_reject_non_huggingface_url(self) -> None:
        with self.assertRaises(ValueError):
            parse_huggingface_url("https://example.com/demo/model")

    def test_normalize_repo_url(self) -> None:
        self.assertEqual(
            normalize_huggingface_url("https://huggingface.co/tewea/demo"),
            "https://hf-mirror.com/tewea/demo/tree/main",
        )

    def test_parse_mirror_url(self) -> None:
        parsed = parse_huggingface_url("https://hf-mirror.com/tewea/demo/tree/main")

        self.assertEqual(parsed.repo_id, "tewea/demo")
        self.assertEqual(parsed.revision, "main")


class BuildDownloadCommandTests(unittest.TestCase):
    def test_build_command_with_revision_and_token(self) -> None:
        request = DownloadRequest(
            repo_id="tewea/z_image_turbo_bf16_nsfw",
            filename="z_image_turbo_bf16_nsfw.safetensors",
            target_dir=r"D:\ComfyUI\models\checkpoints",
            repo_type="model",
            revision="main",
            token="secret-token",
        )

        command = build_hf_download_command(request)

        self.assertEqual(
            command,
            [
                "hf",
                "download",
                "tewea/z_image_turbo_bf16_nsfw",
                "z_image_turbo_bf16_nsfw.safetensors",
                "--repo-type",
                "model",
                "--revision",
                "main",
                "--local-dir",
                r"D:\ComfyUI\models\checkpoints",
                "--token",
                "secret-token",
            ],
        )

    def test_build_command_without_optional_values(self) -> None:
        request = DownloadRequest(
            repo_id="acme/demo",
            filename="weights.bin",
            target_dir=r"D:\Models",
        )

        command = build_hf_download_command(request)

        self.assertEqual(
            command,
            [
                "hf",
                "download",
                "acme/demo",
                "weights.bin",
                "--repo-type",
                "model",
                "--local-dir",
                r"D:\Models",
            ],
        )


class EndpointTests(unittest.TestCase):
    def test_resolve_hf_endpoint_prefers_mirror(self) -> None:
        endpoint = resolve_hf_endpoint("https://huggingface.co/tewea/demo/tree/main")

        self.assertEqual(endpoint, DEFAULT_HF_ENDPOINT)

    def test_build_runtime_env_sets_endpoint(self) -> None:
        env = build_runtime_env("https://hf-mirror.com", DEFAULT_PROXY_STRATEGY)

        self.assertEqual(env["HF_ENDPOINT"], "https://hf-mirror.com")
        self.assertIn("hf-mirror.com", env["NO_PROXY"])
        self.assertNotIn("xethub.hf.co", env["NO_PROXY"])

    def test_build_runtime_env_for_all_direct(self) -> None:
        env = build_runtime_env("https://hf-mirror.com", "all_direct")

        self.assertIn("hf-mirror.com", env["NO_PROXY"])
        self.assertIn("xethub.hf.co", env["NO_PROXY"])
        self.assertIn("cas-bridge.xethub.hf.co", env["NO_PROXY"])

    def test_build_runtime_env_for_all_proxy(self) -> None:
        env = build_runtime_env("https://hf-mirror.com", "all_proxy")

        self.assertEqual(env["HF_ENDPOINT"], "https://hf-mirror.com")
        self.assertNotIn("hf-mirror.com", env.get("NO_PROXY", ""))
        self.assertNotIn("xethub.hf.co", env.get("NO_PROXY", ""))

    def test_proxy_strategies_contains_default(self) -> None:
        strategy_ids = [item["id"] for item in PROXY_STRATEGIES]

        self.assertIn(DEFAULT_PROXY_STRATEGY, strategy_ids)


class ModelDirectoryTests(unittest.TestCase):
    def test_list_model_subdirectories_returns_sorted_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "loras").mkdir()
            (root / "checkpoints").mkdir()
            (root / "README.txt").write_text("not a directory", encoding="utf-8")

            directories = list_model_subdirectories(str(root))

            self.assertEqual(directories, ["checkpoints", "loras"])

    def test_list_model_subdirectories_handles_missing_root(self) -> None:
        directories = list_model_subdirectories(r"D:\missing\hf-comfyui-test")

        self.assertEqual(directories, [])


class LocalPathTests(unittest.TestCase):
    def test_resolve_local_file_path_handles_nested_repo_file(self) -> None:
        file_path = resolve_local_file_path(r"D:\ComfyUI\models\loras", "foo/bar/model.safetensors")

        self.assertEqual(file_path, r"D:\ComfyUI\models\loras\foo\bar\model.safetensors")

    def test_get_download_progress_bytes_prefers_incomplete_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            download_dir = root / ".cache" / "huggingface" / "download"
            download_dir.mkdir(parents=True)
            metadata_path = download_dir / "foo" / "bar" / "model.safetensors.metadata"
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata_path.write_text("", encoding="utf-8")

            from huggingface_hub._local_folder import _short_hash  # type: ignore

            incomplete_path = metadata_path.parent / f"{_short_hash(metadata_path.name)}.etag123.incomplete"
            incomplete_path.write_bytes(b"x" * 256)

            current_size, progress_path = get_download_progress_bytes(str(root), "foo/bar/model.safetensors")

            self.assertEqual(current_size, 256)
            self.assertEqual(Path(progress_path), incomplete_path)

    def test_get_download_progress_bytes_falls_back_to_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            final_file = root / "foo" / "bar" / "model.safetensors"
            final_file.parent.mkdir(parents=True)
            final_file.write_bytes(b"x" * 128)

            current_size, progress_path = get_download_progress_bytes(str(root), "foo/bar/model.safetensors")

            self.assertEqual(current_size, 128)
            self.assertEqual(Path(progress_path), final_file)


class FormatSizeTests(unittest.TestCase):
    def test_format_size_for_gigabytes(self) -> None:
        self.assertEqual(format_size(1073741824), "1.0 GB")


if __name__ == "__main__":
    unittest.main()
