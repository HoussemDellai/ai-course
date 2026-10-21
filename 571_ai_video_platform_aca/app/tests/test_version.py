import re
from pathlib import Path

from fastapi.testclient import TestClient

from fakes import FakeNarrator  # noqa: F401  (ensures tests dir is importable)
from video_platform import version
from video_platform.api import create_app
from video_platform.config import Settings
from video_platform.storage import LocalArtifactStore

ROOT = Path(__file__).parents[1]


def test_version_is_semver_and_defaults_to_1_0_0():
    assert version.SEMVER.match(version.__version__)
    assert (ROOT / "video_platform" / "VERSION").read_text().strip() == version.__version__


def test_version_file_must_be_semver(tmp_path, monkeypatch):
    bad = tmp_path / "VERSION"
    bad.write_text("latest\n")
    monkeypatch.setattr(version, "VERSION_FILE", bad)
    try:
        version.read_version()
    except ValueError as e:
        assert "semantic version" in str(e)
    else:
        raise AssertionError("non-semver VERSION must be rejected")


def test_ui_footer_and_healthz_show_version(tmp_path):
    settings = Settings(work_dir=tmp_path / "work", local_output_dir=tmp_path / "out")
    store = LocalArtifactStore(settings.local_output_dir)

    async def close():
        pass

    app = create_app(settings, services=(store, lambda manager: None, close))
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert f"v{version.__version__}</footer>" in page.text and "{{APP_VERSION}}" not in page.text
        assert client.get("/healthz").json() == {"status": "ok", "version": version.__version__}
        assert app.version == version.__version__


def test_container_image_tag_is_the_app_version():
    acr = (ROOT.parent / "infra" / "acr.tf").read_text()
    assert 'file("${path.module}/../app/video_platform/VERSION")' in acr
    assert re.search(r'app_image_tag\s*=\s*"video-platform:\$\{local\.app_version\}"', acr)
