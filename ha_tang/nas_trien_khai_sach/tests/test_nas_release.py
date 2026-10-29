from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import nas_release  # noqa: E402


class NasReleaseRenderTest(unittest.TestCase):
    def setUp(self):
        self.rendered = nas_release.render_nas_compose((HERE / "compose.yaml").read_text(), "20990101a")

    def test_images_are_pinned_to_tag(self):
        images = [l.split("image:")[1].strip() for l in self.rendered.splitlines() if "image:" in l]
        self.assertEqual(sorted(set(images)), [
            "prj069-nas-backend:20990101a", "prj069-nas-gateway:20990101a", "prj069-nas-web:20990101a"])
        self.assertNotIn("${PRJ069_", self.rendered.replace("${PRJ069_COMPOSE", "").replace("${PRJ069_DATA", "")
                         .replace("${PRJ069_PROFILE", "").replace("${PRJ069_MODEL", "").replace("${PRJ069_BOOTSTRAP", ""))

    def test_cpus_removed_everything_else_kept(self):
        original = (HERE / "compose.yaml").read_text()
        self.assertIn("cpus:", original)
        self.assertNotIn("cpus:", self.rendered)
        self.assertEqual(len(original.splitlines()) - len(self.rendered.splitlines()), original.count("cpus:"))

    def test_apply_compose_formats(self):
        text = nas_release.render_apply_compose()
        self.assertIn("{{.Names}}", text)
        self.assertIn("$$C build", text)
        self.assertNotIn("{host_root}", text)


if __name__ == "__main__":
    unittest.main()
