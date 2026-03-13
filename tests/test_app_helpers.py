import unittest

from app import eta_text, progress_text


class ProgressTextTests(unittest.TestCase):
    def test_progress_text_with_expected_size(self) -> None:
        text = progress_text(512, 1024)

        self.assertEqual(text, "进度: 50.0% (512.0 B / 1.0 KB)")

    def test_progress_text_without_expected_size(self) -> None:
        text = progress_text(2048, 0)

        self.assertEqual(text, "进度: 已下载 2.0 KB")


class EtaTextTests(unittest.TestCase):
    def test_eta_text_with_speed(self) -> None:
        text = eta_text(512, 1024, 128)

        self.assertEqual(text, "剩余时间: 4秒")

    def test_eta_text_without_expected_size(self) -> None:
        text = eta_text(512, 0, 128)

        self.assertEqual(text, "剩余时间: -")


if __name__ == "__main__":
    unittest.main()
