from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from PIL import Image

from video_platform.config import Settings
from video_platform.education_schemas import EducationalScene, TechnicalDiagram
from video_platform.education_visuals import (
    EducationalVisuals, VisualError, _atomic_bytes, _diagram_xml, _io_path, _native_style, _shapes,
)
from video_platform.video_models import VIDEO_MODELS


@pytest.fixture
def artifact_dir():
    folder = Path(__file__).parent / f".education-visuals-{uuid.uuid4().hex}"
    folder.mkdir()
    try:
        yield folder
    finally:
        shutil.rmtree(folder)


@pytest.fixture
def scene():
    return EducationalScene(
        title="Safe title: 100% 'quoted' [text]; %{{}}",
        description="A clear explanation", narration="Narration", image_prompt="A public educational illustration",
        source_ids=["s1"],
    )


@pytest.fixture
def fanin_scene(scene):
    nodes = [
        ("client", "Client", "General User"),
        ("service", "Service\nselector: app: web", "Kubernetes Service"),
        ("deployment", "Deployment\nreplicas: 3", "Kubernetes Deployment"),
        ("replicaset", "ReplicaSet", "Kubernetes ReplicaSet"),
        *[(f"pod{i}", f"Pod {i}\napp: web", "Kubernetes Pod") for i in range(1, 4)],
    ]
    edges = [
        ("client", "service", "Traffic"),
        *[("service", f"pod{i}", "Matching backend") for i in range(1, 4)],
        ("deployment", "replicaset", "Manages"),
        *[("replicaset", f"pod{i}", "Maintains") for i in range(1, 4)],
    ]
    scene.diagram = TechnicalDiagram(
        nodes=[{"id": node, "label": label, "icon_query": query} for node, label, query in nodes],
        edges=[{"source": source, "target": target, "label": label} for source, target, label in edges],
    )
    return scene


def png(width=192, height=128, color="blue"):
    output = BytesIO()
    Image.new("RGB", (width, height), color).save(output, "PNG")
    return output.getvalue()


def test_atomic_write_actual_nested_path_exceeds_legacy_temporary_limit(artifact_dir):
    folder = artifact_dir.resolve()
    while len(str(folder)) < 215:
        folder = folder / ("nested-" + "a" * min(30, 214 - len(str(folder))))
    folder.mkdir(parents=True)
    dest = folder / "scene_001.drawio"
    old_pending = dest.with_name(f".{dest.name}.{'a' * 32}.partial")
    assert len(str(dest)) < 260 < len(str(old_pending))
    _atomic_bytes(dest, b"<mxGraphModel/>")
    assert dest.read_bytes() == b"<mxGraphModel/>"
    _atomic_bytes(dest, b"<mxGraphModel><root/></mxGraphModel>")
    assert dest.read_bytes() == b"<mxGraphModel><root/></mxGraphModel>"
    assert list(folder.iterdir()) == [dest]


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-path filesystem regression")
def test_atomic_write_actual_windows_extended_destination(artifact_dir):
    root = artifact_dir.resolve() / "extended"
    folder = root
    while len(str(folder)) < 270:
        folder = folder / ("nested-" + "b" * 30)
    try:
        _io_path(folder).mkdir(parents=True)
        dest = folder / "scene_001.drawio"
        assert len(str(dest)) > 260
        _atomic_bytes(dest, b"complete")
        assert _io_path(dest).read_bytes() == b"complete"
        assert list(_io_path(folder).iterdir()) == [_io_path(dest)]
    finally:
        shutil.rmtree(_io_path(root))


class Comfy:
    def __init__(self):
        self.calls = []

    async def _render(self, *args):
        self.calls.append(args)
        args[3].write_bytes(png(args[1]["width"], args[1]["height"]))
        if args[7]:
            await args[7]("http://gpu:8188", "prompt-1")
        return args[3]

    async def generate_clip(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        args[3].write_bytes(b"video")
        return args[3]


class Credential:
    def __init__(self):
        self.scopes = []

    async def get_token(self, scope):
        self.scopes.append(scope)
        return SimpleNamespace(token="test-token")


@pytest.fixture
async def visuals():
    instance = EducationalVisuals(Settings(), Comfy(), Credential())
    yield instance
    await instance.aclose()


@pytest.mark.asyncio
async def test_export_actual_nested_path_with_long_pending_png(visuals, artifact_dir, monkeypatch):
    folder = artifact_dir.resolve()
    while len(str(folder)) < 235:
        folder = folder / ("long-" + "x" * min(30, 234 - len(str(folder))))
    folder.mkdir(parents=True)
    editable, dest = folder / "scene_001.drawio", folder / "scene_001.png"
    editable.write_text("<mxGraphModel/>")

    async def export(args, **kwargs):
        output = Path(args[args.index("--output") + 1])
        assert len(str(output)) > 260
        assert not str(output).startswith("\\\\?\\")
        _io_path(output).write_bytes(png(192, 128))

    monkeypatch.setattr("video_platform.education_visuals._run", export)
    visuals.settings = replace(visuals.settings, drawio_export_command='["drawio"]')
    await visuals._export(editable, dest, 192, 128)
    with Image.open(dest) as raster:
        assert raster.size == (192, 128)
    assert sorted(path.name for path in folder.iterdir()) == ["scene_001.drawio", "scene_001.png"]


@pytest.mark.asyncio
async def test_comfy_image_contract_resume_and_callback(visuals, artifact_dir, scene):
    template = artifact_dir / "t2i.json"
    template.write_text(json.dumps({"1": {"class_type": "VerifiedLocalNode", "inputs": {
        key: "{{" + key + "}}" for key in ("prompt", "width", "height", "seed", "filename_prefix")
    }}}))
    visuals.settings = replace(visuals.settings, comfy_image_workflow=str(template))
    submitted = []

    async def callback(server, prompt):
        submitted.append((server, prompt))

    resume = {"server": "http://gpu:8188", "prompt_id": "existing"}
    dest = artifact_dir / "image.png"
    assert await visuals.image(scene, 192, 128, 42, dest, resume, callback) == dest
    call = visuals.comfy.calls[0]
    assert call[1]["prompt"] == scene.image_prompt
    assert call[2] == 42 and call[6] == resume and call[9] is None
    assert submitted == [("http://gpu:8188", "prompt-1")]


@pytest.mark.asyncio
async def test_unconfigured_and_bad_t2i_explicit_failures(visuals, artifact_dir, scene):
    with pytest.raises(VisualError, match="COMFY_IMAGE_WORKFLOW"):
        await visuals.image(scene, 192, 128, 1, artifact_dir / "image.png")
    template = artifact_dir / "bad.json"
    template.write_text(json.dumps({"1": {"inputs": {"image": "{{image}}"}}}))
    visuals.settings = replace(visuals.settings, comfy_image_workflow=str(template))
    with pytest.raises(VisualError, match="T2I template"):
        await visuals.image(scene, 192, 128, 1, artifact_dir / "image.png")
    with pytest.raises(VisualError, match="Unsupported image"):
        await visuals.image(scene, 192, 128, 1, artifact_dir / "image.png", provider="chat")


@pytest.mark.asyncio
async def test_foundry_image_authenticated_documented_surface(visuals, artifact_dir, scene):
    requests = []

    async def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png(1024, 1024)).decode()}]})

    await visuals.http.aclose()
    visuals.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    visuals.settings = replace(visuals.settings, foundry_image_endpoint="https://example.openai.azure.com",
                               foundry_image_model="image deployment")
    await visuals.image(scene, 1024, 1024, 42, artifact_dir / "image.png", provider="foundry")
    request = requests[0]
    assert request.url.path == "/openai/deployments/image deployment/images/generations"
    assert request.url.params["api-version"] == "2025-04-01-preview"
    assert request.headers["authorization"] == "Bearer test-token"
    body = json.loads(request.content)
    assert body["size"] == "1024x1024" and "seed" not in body
    assert visuals.credential.scopes == ["https://cognitiveservices.azure.com/.default"]


@pytest.mark.asyncio
async def test_foundry_capability_checks_before_billing(visuals, artifact_dir, scene):
    visuals.settings = replace(visuals.settings, foundry_image_endpoint="https://example.openai.azure.com",
                               foundry_image_model="gpt-image")
    with pytest.raises(VisualError, match="explicit upscaling"):
        await visuals.image(scene, 3840, 2160, 1, artifact_dir / "image.png", provider="foundry")
    with pytest.raises(VisualError, match="exactly-once"):
        await visuals.image(scene, 1024, 1024, 1, artifact_dir / "image.png", resume={"id": "1"},
                            provider="foundry")
    visuals.settings = replace(visuals.settings, foundry_image_endpoint="https://example/api/projects/private")
    with pytest.raises(VisualError, match="resource root"):
        await visuals.image(scene, 1024, 1024, 1, artifact_dir / "image.png", provider="foundry")


@pytest.mark.asyncio
async def test_foundry_undersized_and_invalid_responses(visuals, artifact_dir, scene):
    visuals.settings = replace(visuals.settings, foundry_image_endpoint="https://example.openai.azure.com",
                               foundry_image_model="gpt-image")
    await visuals.http.aclose()
    visuals.http = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png()).decode()}]})
    ))
    with pytest.raises(VisualError, match="undersized"):
        await visuals.image(scene, 1024, 1024, 1, artifact_dir / "image.png", provider="foundry")
    assert not (artifact_dir / "image.png").exists()


def test_native_style_blocks_remote_and_unsafe_metadata():
    for unsafe in [
        "shape=image;image=https://icons.example/icon.svg;",
        "shape=mxgraph.azure.vm;image=file:///secret;",
        "shape=mxgraph.azure.vm;fillColor=<script>;",
        "shape=unsupported;",
        "",
        "unknownStyle;",
    ]:
        with pytest.raises(VisualError):
            _native_style(unsafe)
    assert _native_style("shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambda;html=1;") == (
        "shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambda;"
    )
    azure = "img/lib/azure2/compute/Kubernetes_Services.svg"
    assert _native_style(f"image;html=1;image=https://app.diagrams.net/{azure};") == (
        f"shape=image;image={azure};"
    )
    with pytest.raises(VisualError):
        _native_style("image;image=https://app.diagrams.net/img/lib/../../private.svg;")
    assert _shapes(SimpleNamespace(isError=False, structuredContent={"shapes": []})) == []
    assert _shapes(SimpleNamespace(isError=False, structuredContent=None, content=[
        SimpleNamespace(type="text", text='[{"style":"shape=mxgraph.azure.vm;"}]')
    ]))[0]["style"] == "shape=mxgraph.azure.vm;"


@pytest.mark.parametrize("source,expected", [
    ("rounded=1;whiteSpace=wrap;html=1;absoluteArcSize=1;arcSize=14;strokeWidth=2;",
     "rounded=1;absoluteArcSize=1;arcSize=14;strokeWidth=2;shape=rectangle;"),
    ("html=1;dashed=0;whiteSpace=wrap;", "dashed=0;shape=rectangle;"),
    ("shape=ellipse;html=1;perimeter=ellipsePerimeter;", "shape=ellipse;"),
    ("ellipse;shape=doubleEllipse;html=1;aspect=fixed;", "shape=doubleEllipse;aspect=fixed;"),
    ("shape=rhombus;html=1;perimeter=rhombusPerimeter;", "shape=rhombus;"),
    ("shape=process;html=1;rounded=1;size=0.14;arcSize=6;",
     "shape=process;rounded=1;size=0.14;arcSize=6;"),
    ("shape=trapezoid;perimeter=trapezoidPerimeter;html=1;size=0.23;arcSize=10;flipV=1;",
     "shape=trapezoid;size=0.23;arcSize=10;flipV=1;"),
    ("ellipse;html=1;", "shape=ellipse;"),
    ("shape=module;align=left;spacingLeft=20;align=center;verticalAlign=top;whiteSpace=wrap;html=1;",
     "shape=module;align=center;verticalAlign=top;"),
])
def test_native_builtin_styles(source, expected):
    assert _native_style(source) == expected


def test_flowchart_process_exact_title_beats_generic_and_predefined_process():
    from video_platform.education_visuals import _shape_candidates

    shapes = [
        {"title": "Activity / Process / Entity / External Interactor", "style": "html=1;dashed=0;"},
        {"title": "Data Process", "style": "shape=ellipse;html=1;"},
        {"title": "Predefined Process", "style": "shape=process;rounded=1;"},
        {"title": "Process", "style": "rounded=1;html=1;arcSize=14;"},
    ]
    assert _shape_candidates("Flowchart Process", shapes)[0] == shapes[-1]


async def test_flowchart_and_uml_component_export_and_restore(
    visuals, artifact_dir, scene, monkeypatch,
):
    scene.diagram = TechnicalDiagram(nodes=[
        {"id": "process", "label": "Evaluate ticket", "icon_query": "Flowchart Process"},
        {"id": "manual", "label": "Human review", "icon_query": "Flowchart Manual Operation"},
        {"id": "component", "label": "AI agent", "icon_query": "UML Component"},
    ], edges=[
        {"source": "process", "target": "manual", "label": "Escalate"},
        {"source": "manual", "target": "component", "label": "Submit"},
    ])
    scene.animation = "reveal"
    searches = []
    metadata = {
        "Flowchart Process": [
            {"title": "Data Process", "style": "shape=ellipse;html=1;"},
            {"title": "Process", "style": "rounded=1;html=1;arcSize=14;"},
        ],
        "Flowchart Manual Operation": [
            {"title": "Manual Operation", "style": "shape=trapezoid;html=1;size=0.23;flipV=1;"},
        ],
        "UML Component": [
            {"title": "Module", "style": "shape=module;align=left;spacingLeft=20;align=center;verticalAlign=top;whiteSpace=wrap;html=1;"},
        ],
    }

    class Session:
        async def call_tool(self, name, arguments):
            if name == "search_shapes":
                searches.append(arguments["query"])
                return SimpleNamespace(isError=False, structuredContent={"shapes": metadata[arguments["query"]]})
            return SimpleNamespace(isError=False)

    @asynccontextmanager
    async def session(url):
        yield Session()

    async def export(args, **kwargs):
        Path(args[args.index("--output") + 1]).write_bytes(png(192, 128))

    monkeypatch.setattr("video_platform.education_visuals._mcp_session", session)
    monkeypatch.setattr("video_platform.education_visuals._run", export)
    visuals.settings = replace(visuals.settings, drawio_mcp_url="http://localhost:3001/mcp",
                               drawio_export_command='["drawio"]')
    dest = artifact_dir / "flowchart.png"
    await visuals.diagram(scene, 192, 128, dest)
    graph = ET.fromstring(dest.with_suffix(".drawio").read_text())
    assert "shape=rectangle;" in graph.find(".//mxCell[@id='node-process']").get("style")
    assert "shape=trapezoid;" in graph.find(".//mxCell[@id='node-manual']").get("style")
    assert "shape=module;" in graph.find(".//mxCell[@id='node-component']").get("style")
    for key, path in visuals.companion_assets(dest, scene).items():
        if key.startswith("reveal_"):
            path.unlink()
    await visuals.restore_reveals(dest, scene, 192, 128)
    assert searches == list(metadata)
    assert all(path.is_file() for path in visuals.companion_assets(dest, scene).values())


def test_native_icon_exact_title_beats_upstream_phonetic_search():
    from video_platform.education_visuals import _shape_candidates

    shapes = [
        {"title": "Azure SQL DataWarehouse", "style": "shape=mxgraph.azure.datawarehouse;"},
        {"title": "SQL Database", "style": "shape=mxgraph.azure.sql_database;"},
        {"title": "SQL Database", "style": "image;image=img/lib/azure2/databases/SQL_Database.svg;"},
    ]
    selected = _shape_candidates("Azure SQL Database", shapes)
    assert selected[0]["style"].endswith("SQL_Database.svg;")
    assert selected[-1]["title"] == "Azure SQL DataWarehouse"
    assert _shape_candidates("General User", [
        {"title": "Authenticated User", "style": "shape=mxgraph.aws4.authenticated_user;"},
        {"title": "User", "style": "shape=mxgraph.aws4.user;"},
    ])[0]["title"] == "User"


@pytest.mark.parametrize("query,resource", [
    ("Kubernetes Service", "svc"), ("Kubernetes Deployment", "deploy"),
    ("Kubernetes ReplicaSet", "rs"), ("Kubernetes Pod", "pod"),
])
def test_native_kubernetes_resource_semantics_beat_generic_cloud(query, resource):
    from video_platform.education_visuals import _kubernetes_resource, _shape_candidates

    native = {"title": resource.upper(), "style": f"shape=mxgraph.kubernetes.icon2;prIcon={resource};"}
    shapes = [
        {"title": query, "style": "shape=image;image=img/lib/azure2/compute/Container_Group.svg;"},
        {"title": "API", "style": "shape=mxgraph.kubernetes.icon2;prIcon=api;"},
        native,
    ]
    assert _kubernetes_resource(query) == resource
    assert _shape_candidates(query, shapes)[0] == native
    assert _shape_candidates(query, shapes[:-1]) == []
    assert _kubernetes_resource("Azure Kubernetes Services") is None


def test_approved_fanin_graph_has_distinct_ports_buses_and_stable_reveals(fanin_scene):
    diagram = fanin_scene.diagram
    styles = ["shape=mxgraph.kubernetes.icon2;prIcon=pod;"] * len(diagram.nodes)
    full = ET.fromstring(_diagram_xml(fanin_scene, styles, 1920, 1080))
    partial = ET.fromstring(_diagram_xml(fanin_scene, styles, 1920, 1080, visible=5))
    edges = full.findall(".//mxCell[@edge='1']")
    assert len(diagram.nodes) == 7 and len(edges) == 8
    assert [(edge.get("source"), edge.get("target"), edge.get("value")) for edge in edges] == [
        (f"node-{edge.source}", f"node-{edge.target}", edge.label) for edge in diagram.edges
    ]
    pairs = [dict(part.split("=", 1) for part in edge.get("style").split(";") if "=" in part) for edge in edges]
    for source in ("service", "replicaset"):
        indices = [i for i, edge in enumerate(diagram.edges) if edge.source == source]
        assert len({pairs[i]["exitY"] for i in indices}) == 3
    assert pairs[1]["sourceJettySize"] != pairs[5]["sourceJettySize"]
    for pod in ("pod1", "pod2", "pod3"):
        indices = [i for i, edge in enumerate(diagram.edges) if edge.target == pod]
        assert len({pairs[i]["entryY"] for i in indices}) == 2
        assert len({pairs[i]["strokeColor"] for i in indices}) == 2
    for i in (0, 1, 4, 5):
        edge = partial.find(f".//mxCell[@id='edge-{i}']")
        assert edge.get("style") == edges[i].get("style")
        assert edge.find("mxGeometry").attrib == edges[i].find("mxGeometry").attrib
        assert partial.find(f".//mxCell[@id='edge-label-{i}']/mxGeometry").attrib == full.find(
            f".//mxCell[@id='edge-label-{i}']/mxGeometry"
        ).attrib
    assert all(int(style["fontSize"]) <= 24 for style in pairs)
    captions = [full.find(f".//mxCell[@id='edge-label-{i}']") for i in range(8)]
    assert [cell.get("value") for cell in captions] == [edge.label for edge in diagram.edges]

    def rectangle(cell):
        geometry = cell.find("mxGeometry")
        return tuple(float(geometry.get(key)) for key in ("x", "y", "width", "height"))

    def overlaps(left, right):
        x, y, width, height = left
        rx, ry, rw, rh = right
        return x < rx + rw and rx < x + width and y < ry + rh and ry < y + height

    boxes = [rectangle(cell) for cell in captions]
    nodes = [rectangle(full.find(f".//mxCell[@id='{prefix}{node.id}']"))
             for node in diagram.nodes for prefix in ("node-", "label-")]
    assert not any(overlaps(box, other) for i, box in enumerate(boxes) for other in boxes[i + 1:])
    assert not any(overlaps(box, node) for box in boxes for node in nodes)


def test_fanin_typography_scales_with_true_4k_canvas(fanin_scene):
    styles = ["shape=mxgraph.kubernetes.icon2;prIcon=pod;"] * 7
    graphs = [ET.fromstring(_diagram_xml(fanin_scene, styles, width, height))
              for width, height in ((1920, 1080), (3840, 2160))]
    for cell_id in ("label-service", "edge-label-1", "edge-label-5"):
        fonts = [dict(part.split("=", 1) for part in graph.find(
            f".//mxCell[@id='{cell_id}']"
        ).get("style").split(";") if "=" in part)["fontSize"] for graph in graphs]
        assert int(fonts[1]) >= int(fonts[0]) * 2


@pytest.mark.asyncio
async def test_kubernetes_search_uses_verified_resource_aliases_and_replaces_legacy_cache(
    visuals, artifact_dir, fanin_scene, monkeypatch,
):
    calls = []

    class Session:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            if name == "create_diagram":
                return SimpleNamespace(isError=False)
            resource = arguments.get("query", "").split()[-1]
            style = (f"shape=mxgraph.kubernetes.icon2;prIcon={resource};"
                     if arguments.get("query", "").startswith("Kubernetes ")
                     else "shape=mxgraph.aws4.user;")
            return SimpleNamespace(isError=False, structuredContent={"shapes": [{"style": style}]})

    @asynccontextmanager
    async def session(url):
        yield Session()

    async def export(args, **kwargs):
        Path(args[args.index("--output") + 1]).write_bytes(png(192, 128))

    monkeypatch.setattr("video_platform.education_visuals._mcp_session", session)
    monkeypatch.setattr("video_platform.education_visuals._run", export)
    visuals.settings = replace(visuals.settings, drawio_mcp_url="http://127.0.0.1:3001/mcp",
                               drawio_export_command='["drawio"]')
    visuals._shape_cache["Kubernetes Service"] = "shape=mxgraph.azure.container_group;"
    dest = artifact_dir / "diagram.png"
    await visuals.diagram(fanin_scene, 192, 128, dest)
    assert [arguments["query"] for name, arguments in calls if name == "search_shapes"] == [
        "General User", "Kubernetes svc", "Kubernetes deploy", "Kubernetes rs", "Kubernetes pod",
    ]
    graph = ET.fromstring(dest.with_suffix(".drawio").read_text())
    for node, resource in (("service", "svc"), ("deployment", "deploy"), ("replicaset", "rs")):
        assert f"prIcon={resource};" in graph.find(f".//mxCell[@id='node-{node}']").get("style")


def test_diagram_fork_layout_and_reveals_keep_positions(scene):
    scene.diagram = TechnicalDiagram(nodes=[
        {"id": "app", "label": "Application", "icon_query": "Azure Kubernetes"},
        {"id": "sql", "label": "SQL database", "icon_query": "Azure SQL Database"},
        {"id": "blob", "label": "Storage", "icon_query": "Azure Storage"},
    ], edges=[
        {"source": "app", "target": "sql", "label": "queries"},
        {"source": "app", "target": "blob", "label": "stores"},
    ])
    styles = ["shape=mxgraph.azure.virtual_machine;"] * 3
    full = ET.fromstring(_diagram_xml(scene, styles, 1920, 1080))
    first = ET.fromstring(_diagram_xml(scene, styles, 1920, 1080, visible=1))
    app = full.find(".//mxCell[@id='node-app']/mxGeometry")
    sql = full.find(".//mxCell[@id='node-sql']/mxGeometry")
    blob = full.find(".//mxCell[@id='node-blob']/mxGeometry")
    assert float(app.get("x")) < float(sql.get("x")) == float(blob.get("x"))
    assert float(sql.get("y")) < float(app.get("y")) < float(blob.get("y"))
    assert first.find(".//mxCell[@id='node-app']/mxGeometry").attrib == app.attrib
    for edge in full.findall(".//mxCell[@edge='1']"):
        assert "entryX=0;entryY=0.5;" in edge.get("style")
        assert edge.find("mxGeometry").get("x") == "0.6"


@pytest.mark.asyncio
async def test_diagram_private_mcp_native_xml_export_and_reveals(visuals, artifact_dir, scene, monkeypatch):
    scene.diagram = TechnicalDiagram(nodes=[
        {"id": "vm", "label": "VM <safe> & exact", "icon_query": "Azure VM"},
        {"id": "db", "label": "Database", "icon_query": "Azure SQL"},
    ], edges=[{"source": "vm", "target": "db", "label": "reads"}])
    scene.animation = "reveal"
    calls, exports = [], []

    class Session:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return SimpleNamespace(isError=False, structuredContent={
                "shapes": [{"style": "shape=mxgraph.azure.virtual_machine;"}]
            })

    @asynccontextmanager
    async def session(url):
        assert url == "http://127.0.0.1:3001/mcp"
        yield Session()

    async def export(args, **kwargs):
        output = Path(args[args.index("--output") + 1])
        source = Path(args[-1])
        exports.append(ET.fromstring(source.read_text()))
        output.write_bytes(png(192, 128))

    monkeypatch.setattr("video_platform.education_visuals._mcp_session", session)
    monkeypatch.setattr("video_platform.education_visuals._run", export)
    visuals.settings = replace(visuals.settings, drawio_mcp_url="http://127.0.0.1:3001/mcp",
                               drawio_export_command='["drawio"]')
    dest = artifact_dir / "diagram.png"
    await visuals.diagram(scene, 192, 128, dest)
    assert [name for name, _ in calls] == ["search_shapes", "search_shapes", "create_diagram"]
    assert dest.with_suffix(".drawio").is_file()
    assert Image.open(dest).size == (192, 128)
    assert len(exports) == 3
    first = exports[0]
    assert first.find(".//mxCell[@id='node-db']") is None
    assert first.find(".//mxCell[@id='edge-0']") is None
    assert exports[-1].find(".//mxCell[@id='label-vm']").get("value") == "VM <safe> & exact"
    await visuals.diagram(scene, 192, 128, dest)
    assert sum(name == "search_shapes" for name, _ in calls) == 2  # permitted metadata cached
    assert not list(artifact_dir.glob("*.reveal-*.drawio"))
    companions = visuals.companion_assets(dest, scene)
    assert companions == {
        "diagram_xml": artifact_dir / "diagram.drawio",
        "reveal_01": artifact_dir / "diagram.reveal-01.png",
        "reveal_02": artifact_dir / "diagram.reveal-02.png",
    }
    for key, path in companions.items():
        if key.startswith("reveal_"):
            path.unlink()
    previous_calls = len(calls)
    await visuals.restore_reveals(dest, scene, 192, 128)
    assert len(calls) == previous_calls  # disk-only recovery: no MCP or paid provider submission
    assert all(path.is_file() for path in companions.values())
    for key, path in companions.items():
        if key.startswith("reveal_"):
            path.unlink()
    companions["diagram_xml"].write_text('<!DOCTYPE root [<!ENTITY x "bad">]><mxGraphModel/>')
    with pytest.raises(VisualError, match="prohibited XML"):
        await visuals.restore_reveals(dest, scene, 192, 128)


@pytest.mark.asyncio
async def test_diagram_public_or_missing_configuration_fails(visuals, artifact_dir, scene):
    scene.diagram = TechnicalDiagram(nodes=[{"id": "a", "label": "A", "icon_query": "Azure VM"}])
    with pytest.raises(VisualError, match="DRAWIO_MCP_URL"):
        await visuals.diagram(scene, 192, 128, artifact_dir / "diagram.png")
    visuals.settings = replace(visuals.settings, drawio_mcp_url="https://mcp.draw.io/mcp")
    with pytest.raises(VisualError, match="Public draw.io"):
        await visuals.diagram(scene, 192, 128, artifact_dir / "diagram.png")
    with pytest.raises(VisualError, match="technical diagrams"):
        await visuals.image(scene, 192, 128, 1, artifact_dir / "diagram.png")


@pytest.mark.asyncio
async def test_comfy_motion_uses_i2v_pool(visuals, artifact_dir):
    source, dest = artifact_dir / "input.png", artifact_dir / "clip.mp4"
    source.write_bytes(png())
    resume = {"server": "http://gpu:8188", "prompt_id": "old"}
    await visuals.motion(source, "gentle motion", VIDEO_MODELS["wan22"], 42, dest, resume=resume)
    args, kwargs = visuals.comfy.calls[0]
    assert args[0] == VIDEO_MODELS["wan22"] and args[2] == 42
    assert kwargs["start_image"] == source and kwargs["resume"] == resume
    assert (kwargs["width"], kwargs["height"]) == (1280, 720)
    assert kwargs["upload_subfolder"].startswith("education/")
    assert args[4] == f"{kwargs['upload_subfolder']}/{dest.stem}"
    first_namespace = kwargs["upload_subfolder"]
    other = artifact_dir / "other-job" / "clip.mp4"
    await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 42, other)
    assert visuals.comfy.calls[-1][1]["upload_subfolder"] != first_namespace
    await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 42, dest,
                         upload_subfolder="aivideo/job-unique")
    assert visuals.comfy.calls[-1][1]["upload_subfolder"] == "aivideo/job-unique"
    assert visuals.comfy.calls[-1][0][4] == "aivideo/job-unique/clip"
    source.write_bytes(png(128, 192))
    await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 1, dest)
    assert (visuals.comfy.calls[-1][1]["width"], visuals.comfy.calls[-1][1]["height"]) == (720, 1280)
    await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 1, dest, width=1080, height=1920)
    assert (visuals.comfy.calls[-1][1]["width"], visuals.comfy.calls[-1][1]["height"]) == (1080, 1920)
    with pytest.raises(VisualError, match="supplied together"):
        await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 1, dest, width=1080)


@pytest.mark.asyncio
async def test_foundry_motion_submit_callback_and_reattach(visuals, artifact_dir):
    source, dest = artifact_dir / "input.png", artifact_dir / "clip.mp4"
    source.write_bytes(png())
    requests, submitted = [], []

    async def handler(request):
        requests.append(request)
        if request.method == "POST":
            assert b'inpaint_items' in request.content and b'input.png' in request.content
            return httpx.Response(200, json={"id": "job-1"})
        if "/jobs/" in request.url.path:
            return httpx.Response(200, json={"status": "succeeded", "generations": [{"id": "generation-1"}]})
        return httpx.Response(200, content=b"verified-provider-video")

    async def callback(server, prompt):
        submitted.append({"server": server, "prompt_id": prompt})

    visuals.settings = replace(visuals.settings, foundry_video_endpoint="https://example.openai.azure.com",
                               foundry_video_model="sora-preview")
    await visuals.http.aclose()
    visuals.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 42, dest,
                         provider="foundry", on_submitted=callback)
    assert requests[0].url.path == "/openai/v1/video/generations/jobs"
    assert requests[0].url.params["api-version"] == "preview"
    await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 42, dest,
                         provider="foundry", resume=submitted[0])
    assert sum(r.method == "POST" for r in requests) == 1
    assert dest.read_bytes() == b"verified-provider-video"
    assert set(visuals.credential.scopes) == {"https://ai.azure.com/.default"}


@pytest.mark.asyncio
async def test_foundry_motion_unavailable_region_does_not_retry(visuals, artifact_dir):
    source = artifact_dir / "input.png"
    source.write_bytes(png())
    visuals.settings = replace(visuals.settings, foundry_video_endpoint="https://example.openai.azure.com",
                               foundry_video_model="unavailable-sora")
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(404, json={"error": {"code": "DeploymentNotFound"}})

    await visuals.http.aclose()
    visuals.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(VisualError, match="unavailable.*region"):
        await visuals.motion(source, "motion", VIDEO_MODELS["wan22"], 1, artifact_dir / "clip.mp4",
                             provider="foundry")
    assert len(calls) == 1


def local_font():
    candidates = [
        Path("C:\\Windows\\Fonts\\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    return next((path for path in candidates if path.is_file()), None)


@pytest.mark.asyncio
@pytest.mark.parametrize("animation", ["zoom_in", "zoom_out", "pan", "reveal"])
async def test_real_ffmpeg_animation(visuals, artifact_dir, scene, animation):
    font = local_font()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe") or font is None:
        pytest.skip("Real ffmpeg/ffprobe/local font required")
    visuals.settings = replace(visuals.settings, education_font=str(font))
    scene.animation = animation
    source, dest = artifact_dir / "source.png", artifact_dir / "clip.mp4"
    source.write_bytes(png())
    assert await visuals.animate(source, scene, 1.0, 192, 128, 12, dest) == dest
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(dest)
    ]))
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"], stream["nb_frames"]) == (192, 128, "12")
    assert stream["r_frame_rate"] == "12/1"
    assert not list(artifact_dir.glob(".*"))


@pytest.mark.asyncio
async def test_real_progressive_reveal_preserves_timing(visuals, artifact_dir, scene):
    font = local_font()
    if not shutil.which("ffmpeg") or font is None:
        pytest.skip("Real ffmpeg/local font required")
    visuals.settings = replace(visuals.settings, education_font=str(font))
    scene.animation = "reveal"
    scene.diagram = TechnicalDiagram(nodes=[
        {"id": "a", "label": "A", "icon_query": "Azure VM"},
        {"id": "b", "label": "B", "icon_query": "Azure SQL"},
    ])
    source, dest = artifact_dir / "diagram.png", artifact_dir / "reveal.mp4"
    source.write_bytes(png())
    source.with_name("diagram.reveal-01.png").write_bytes(png(color="red"))
    source.with_name("diagram.reveal-02.png").write_bytes(png(color="blue"))
    await visuals.animate(source, scene, 2.0, 192, 128, 12, dest)
    for time, dominant in [("0.6", 0), ("1.5", 2)]:
        pixels = subprocess.check_output([
            "ffmpeg", "-v", "error", "-ss", time, "-i", str(dest),
            "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ])
        assert pixels[dominant] > 180
        assert pixels[2 - dominant] < 40


@pytest.mark.asyncio
async def test_animate_recovers_reveal_stages_from_persisted_drawio(visuals, artifact_dir, scene, monkeypatch):
    font = local_font()
    if not shutil.which("ffmpeg") or font is None:
        pytest.skip("Real ffmpeg/local font required")
    from video_platform.education_visuals import _diagram_xml

    visuals.settings = replace(visuals.settings, education_font=str(font))
    scene.animation = "reveal"
    scene.diagram = TechnicalDiagram(nodes=[
        {"id": "a", "label": "A", "icon_query": "Azure VM"},
        {"id": "b", "label": "B", "icon_query": "Azure SQL"},
    ])
    source, dest = artifact_dir / "restored.png", artifact_dir / "restored.mp4"
    source.write_bytes(png())
    source.with_suffix(".drawio").write_text(_diagram_xml(
        scene, ["shape=mxgraph.azure.virtual_machine;"] * 2, 192, 128,
    ))
    exports = []

    async def export(editable, target, width, height):
        exports.append(target.name)
        target.write_bytes(png(width, height, "red" if len(exports) == 1 else "blue"))

    monkeypatch.setattr(visuals, "_export", export)
    await visuals.animate(source, scene, 1, 192, 128, 12, dest)
    assert exports == ["restored.reveal-01.png", "restored.reveal-02.png"]
    assert dest.is_file()
    assert not list(artifact_dir.glob("*.reveal-*.drawio"))
    # Second playback uses local companion PNGs and does not export again.
    await visuals.animate(source, scene, 1, 192, 128, 12, dest)
    assert len(exports) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("width,height", [(1920, 1080), (3840, 2160)])
async def test_real_canvas_dimensions_no_upscaling(visuals, artifact_dir, scene, width, height):
    font = local_font()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe") or font is None:
        pytest.skip("Real ffmpeg/ffprobe/local font required")
    visuals.settings = replace(visuals.settings, education_font=str(font))
    source, dest = artifact_dir / "native.png", artifact_dir / "native.mp4"
    source.write_bytes(png(width, height))
    await visuals.animate(source, scene, 2 / 24, width, height, 24, dest)
    probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(dest),
    ]))
    stream = probe["streams"][0]
    assert (stream["width"], stream["height"], stream["nb_frames"]) == (width, height, "2")
    assert stream["r_frame_rate"] == "24/1"
    assert Image.open(source).size == (width, height)


@pytest.mark.asyncio
async def test_animation_rejects_silent_upscaling_and_missing_font(visuals, artifact_dir, scene):
    source = artifact_dir / "source.png"
    source.write_bytes(png())
    with pytest.raises(VisualError, match="not native resolution"):
        await visuals.animate(source, scene, 1, 3840, 2160, 24, artifact_dir / "out.mp4")
    with pytest.raises(VisualError, match="EDUCATION_FONT"):
        await visuals.animate(source, scene, 1, 192, 128, 24, artifact_dir / "out.mp4")


def test_export_wrapper_bounded_cleanup_on_timeout(artifact_dir, monkeypatch):
    from drawio_runtime import export

    source, dest = artifact_dir / "diagram.drawio", artifact_dir / "diagram.png"
    source.write_text("<mxGraphModel/>")
    monkeypatch.setattr("sys.argv", [
        "export.py", "--export", "--format", "png", "--output", str(dest),
        "--width", "192", "--height", "128", "--border", "0", str(source),
    ])
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1] == "run":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(export.subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired):
        export.main()
    first, cleanup = calls
    name = first[0][first[0].index("--name") + 1]
    assert cleanup[0] == ["docker", "rm", "--force", name]
    assert (first[1]["timeout"], cleanup[1]["timeout"]) == (100, 10)
    assert "--network=none" in first[0]
    assert not list(artifact_dir.glob(".drawio-home-*"))


def test_qwen_t2i_workflow_core_schema_and_links():
    from video_platform.comfyui import fill_workflow, load_workflow
    from video_platform.education_visuals import QWEN_T2I_WORKFLOW

    graph = fill_workflow(load_workflow(QWEN_T2I_WORKFLOW), {
        "prompt": "Public illustration", "width": 1920, "height": 1088,
        "seed": 42, "filename_prefix": "education/test",
    })
    # Required core-node names/ports verified against ComfyUI nodes.py,
    # nodes_model_advanced.py and nodes_sd3.py; no GPU imports or custom nodes.
    schema = {
        "UNETLoader": ({"unet_name", "weight_dtype"}, ["MODEL"]),
        "CLIPLoader": ({"clip_name", "type", "device"}, ["CLIP"]),
        "VAELoader": ({"vae_name"}, ["VAE"]),
        "CLIPTextEncode": ({"clip", "text"}, ["CONDITIONING"]),
        "ModelSamplingAuraFlow": ({"model", "shift"}, ["MODEL"]),
        "EmptySD3LatentImage": ({"width", "height", "batch_size"}, ["LATENT"]),
        "KSampler": ({"model", "seed", "steps", "cfg", "sampler_name", "scheduler",
                      "positive", "negative", "latent_image", "denoise"}, ["LATENT"]),
        "VAEDecode": ({"samples", "vae"}, ["IMAGE"]),
        "SaveImage": ({"images", "filename_prefix"}, []),
    }
    expected_ports = {
        "clip": "CLIP", "model": "MODEL", "positive": "CONDITIONING", "negative": "CONDITIONING",
        "latent_image": "LATENT", "samples": "LATENT", "vae": "VAE", "images": "IMAGE",
    }
    assert len(graph) == 10
    for node in graph.values():
        required, _ = schema[node["class_type"]]
        assert set(node["inputs"]) == required
        for key, value in node["inputs"].items():
            if isinstance(value, list):
                origin, port = value
                assert schema[graph[origin]["class_type"]][1][port] == expected_ports[key]
            else:
                assert not isinstance(value, str) or "{{" not in value
    assert graph["1"]["inputs"]["unet_name"] == "qwen_image_fp8_e4m3fn.safetensors"
    assert graph["2"]["inputs"]["clip_name"] == "qwen_2.5_vl_7b_fp8_scaled.safetensors"
    assert graph["3"]["inputs"]["vae_name"] == "qwen_image_vae.safetensors"
    assert (graph["8"]["inputs"]["steps"], graph["8"]["inputs"]["cfg"]) == (20, 4.0)
    assert graph["6"]["inputs"]["shift"] == 3.1
    assert graph["7"]["inputs"]["height"] == 1088
    assert not any(n["class_type"] == "LoadImage" for n in graph.values())


@pytest.mark.asyncio
async def test_bundled_qwen_rounds_up_canvas_alignment(visuals, artifact_dir, scene):
    from video_platform.education_visuals import QWEN_T2I_WORKFLOW

    visuals.settings = replace(visuals.settings, comfy_image_workflow=str(QWEN_T2I_WORKFLOW))
    target = artifact_dir / "qwen.png"
    await visuals.image(scene, 1920, 1080, 42, target)
    assert (visuals.comfy.calls[0][1]["width"], visuals.comfy.calls[0][1]["height"]) == (1920, 1088)
    assert Image.open(target).size == (1920, 1088)


def test_native_export_no_docker_and_bounded_process_group(artifact_dir, monkeypatch):
    from drawio_runtime import export_native
    from video_platform.education_visuals import _diagram_xml

    scene = EducationalScene(
        title="Title", description="Description", narration="Narration", image_prompt="Illustration",
        source_ids=["s1"], diagram=TechnicalDiagram(nodes=[
            {"id": "a", "label": "A", "icon_query": "Azure VM"},
        ]),
    )
    source, dest = artifact_dir / "native.drawio", artifact_dir / "native.png"
    source.write_text(_diagram_xml(scene, [
        "shape=image;image=img/lib/azure2/compute/Virtual_Machine.svg;",
    ], 192, 128))
    export_native._validate(source)
    monkeypatch.setattr(export_native, "SUPPORTED", True)
    runtime_root = artifact_dir / "linux-local"
    monkeypatch.setenv("DRAWIO_RUNTIME_DIR", str(runtime_root))
    monkeypatch.setattr("sys.argv", [
        "export_native.py", "--export", "--format", "png", "--output", str(dest),
        "--width", "192", "--height", "128", "--border", "0", str(source),
    ])
    calls, terminated = [], []

    class Process:
        pid = 12345

        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

        def wait(self, timeout):
            assert timeout == 100
            raise subprocess.TimeoutExpired(calls[-1][0], timeout)

    monkeypatch.setattr(export_native.subprocess, "Popen", Process)
    monkeypatch.setattr(export_native, "_terminate", lambda proc: terminated.append(proc.pid))
    with pytest.raises(subprocess.TimeoutExpired):
        export_native.main()
    command, options = calls[0]
    assert command[:4] == ["timeout", "--signal=TERM", "--kill-after=5", "90"]
    assert "xvfb-run" in command and "docker" not in command
    assert "--disable-dev-shm-usage" in command
    assert options["start_new_session"] is True
    assert Path(options["env"]["HOME"]).parent == runtime_root
    assert options["env"]["TMPDIR"] == options["env"]["HOME"]
    assert not list(runtime_root.iterdir())
    assert terminated == [12345]
    assert not dest.exists()
    source.write_text('<!DOCTYPE root [<!ENTITY x "bad">]><mxGraphModel/>')
    with pytest.raises(ValueError, match="prohibited"):
        export_native._validate(source)
    source.write_text(
        '<mxGraphModel><root><mxCell style="html=0;image=https://bad.example/icon.svg;"/>'
        '</root></mxGraphModel>'
    )
    with pytest.raises(ValueError, match="External assets"):
        export_native._validate(source)
