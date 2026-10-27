from html.parser import HTMLParser
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from video_platform.api import create_app
from video_platform.config import Settings
from video_platform.storage import LocalArtifactStore


class BrandMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        work_dir=tmp_path / "work", local_output_dir=tmp_path / "out", api_key="test-key",
    )
    store = LocalArtifactStore(settings.local_output_dir)

    async def close():
        pass

    app = create_app(settings, services=(store, lambda manager: None, close))
    with TestClient(app) as test_client:
        yield test_client


def test_header_hero_and_favicon_use_brand_assets(client):
    page = client.get("/")
    assert page.status_code == 200
    elements = BrandMarkup(page.text).elements
    favicon = next(attrs for tag, attrs in elements if tag == "link" and attrs.get("rel") == "icon")
    assert favicon["type"] == "image/svg+xml"
    assert favicon["sizes"] == "any"
    assert favicon["href"] == "/brand/icon.svg"
    images = [attrs for tag, attrs in elements if tag == "img" and attrs.get("class") == "logo"]
    assert [(image["src"], image["alt"]) for image in images] == [
        ("/brand/logo.svg", "AI Video Platform"), ("/brand/icon.svg", ""),
    ]
    assert images[1]["aria-hidden"] == "true"
    assert any(
        tag == "source" and attrs.get("media") == "(max-width: 520px)"
        and attrs.get("srcset") == favicon["href"]
        for tag, attrs in elements
    )
    assert any(
        tag == "a" and attrs.get("class") == "brand" and attrs.get("href") == "#"
        and attrs.get("aria-label") == "AI Video Platform - New video"
        for tag, attrs in elements
    )


@pytest.mark.parametrize(("filename", "viewbox"), [("icon.svg", "0 0 64 64"), ("logo.svg", "0 0 224 64")])
def test_brand_assets_are_public_scalable_and_cacheable(client, filename, viewbox):
    response = client.get(f"/brand/{filename}")
    assert response.status_code == 200
    assert response.headers["content-type"].split(";")[0] == "image/svg+xml"
    svg = ElementTree.fromstring(response.content)
    assert svg.tag == "{http://www.w3.org/2000/svg}svg"
    assert svg.attrib["viewBox"] == viewbox
    assert svg.find("{http://www.w3.org/2000/svg}title").text
    cached = client.get(f"/brand/{filename}", headers={"If-None-Match": response.headers["etag"]})
    assert cached.status_code == 304
    assert cached.content == b""


def test_public_brand_assets_do_not_expose_other_files_or_bypass_api_auth(client):
    assert client.get("/brand/index.html").status_code == 404
    assert client.get("/brand/%2e%2e/VERSION").status_code == 404
    assert client.get("/api/videos").status_code == 401
    assert client.get("/api/videos", headers={"X-API-Key": "test-key"}).status_code == 200
