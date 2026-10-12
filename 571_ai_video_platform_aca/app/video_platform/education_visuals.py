"""Bounded visual adapters; generated pictures are never used for technical labels.

Foundry image configuration is an Azure OpenAI resource endpoint and a GPT-image
deployment (not a chat deployment). Video configuration targets the documented
Azure preview I2V jobs API. Neither adapter automatically retries a paid POST.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import tempfile
import uuid
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager, contextmanager
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote, urlsplit

import httpx
from PIL import Image

from .comfyui import IMAGE_EXTENSIONS, ComfyUIPool, SubmittedCallback, fill_workflow, load_workflow
from .config import Settings
from .education_schemas import EducationalScene
from .video_models import VideoModel

# Base (no LoRA) branch of Comfy-Org/workflow_templates image_qwen_image.json
# revision 8be1f8c4b5af2d550d70922a23b79cee599e1f3e: 20 steps, CFG 4, shift 3.1.
QWEN_T2I_WORKFLOW = Path(__file__).parent / "comfy_workflows" / "qwen_image_t2i.json"

class VisualError(RuntimeError):
    """Actionable configuration, capability, or rendering failure."""


def _canvas(width: int, height: int) -> None:
    if not (16 <= width <= 7680 and 16 <= height <= 7680 and width * height <= 34_000_000):
        raise VisualError("Canvas must be 16–7680 pixels per side, at most 34 million pixels")


def _size(path: Path) -> tuple[int, int]:
    try:
        with Image.open(_io_path(path)) as image:
            if image.width * image.height > 50_000_000:
                raise VisualError("Visual source exceeds the 50 million pixel decoding limit")
            image.verify()
            return image.size
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise VisualError(f"Invalid visual image: {path.name}") from exc


def _sufficient(path: Path, width: int, height: int) -> None:
    source = _size(path)
    if source[0] < width or source[1] < height:
        raise VisualError(
            f"Source is {source[0]}x{source[1]}, smaller than canvas {width}x{height}; "
            "select explicit upscaling or a smaller canvas. This is not native resolution."
        )


def _io_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    absolute = str(path.resolve())
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)


def _atomic_bytes(dest: Path, data: bytes) -> None:
    # Keep temporary names independent of destination length; use extended
    # Windows paths only for filesystem calls, never external tool arguments.
    target = _io_path(dest)
    pending = _io_path(dest.with_name(f".{uuid.uuid4().hex}"))
    try:
        pending.write_bytes(data)
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)


@contextmanager
def _temporary_diagram(folder: Path, xml: str) -> Iterator[Path]:
    with tempfile.NamedTemporaryFile(
        mode="wb", prefix="", suffix=".drawio", dir=_io_path(folder), delete=False,
    ) as file:
        pending = Path(file.name)
        try:
            file.write(xml.encode("utf-8"))
            file.close()
            yield folder / pending.name
        finally:
            file.close()
            pending.unlink(missing_ok=True)


def _endpoint(value: str, label: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path.strip("/")):
        raise VisualError(f"{label} must be an HTTPS Azure OpenAI resource root URL, not a project/chat URL")
    return value.rstrip("/")


def _command(value: str) -> list[str]:
    if not value.strip():
        raise VisualError("Set DRAWIO_EXPORT_COMMAND to a local headless draw.io export executable")
    try:
        # JSON argv is unambiguous on Windows, including spaces in executable paths.
        args = json.loads(value) if value.lstrip().startswith("[") else shlex.split(value, posix=False)
    except (ValueError, json.JSONDecodeError) as exc:
        raise VisualError("DRAWIO_EXPORT_COMMAND must be an executable or a JSON argv array") from exc
    if not isinstance(args, list) or not args or any(not isinstance(a, str) or not a for a in args):
        raise VisualError("DRAWIO_EXPORT_COMMAND must contain nonempty string arguments")
    return [a[1:-1] if len(a) >= 2 and a[0] == a[-1] == '"' else a for a in args]


async def _run(args: list[str], *, cwd: Path | None = None, timeout: float = 600) -> None:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args, cwd=cwd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
    except OSError as exc:
        raise VisualError(f"Executable unavailable: {args[0]}") from exc
    try:
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout)
    except (TimeoutError, asyncio.CancelledError):
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
        raise
    if proc.returncode:
        raise VisualError(f"{Path(args[0]).name} failed: {stderr.decode(errors='replace')[-2000:]}")


def _native_style(style: Any) -> str:
    """Accept local built-in stencil metadata, never URLs, HTML, or file references."""
    if not isinstance(style, str) or len(style) > 3000:
        raise VisualError("Shape search returned invalid native style metadata")
    if any(c in style for c in "<>&\\\r\n"):
        raise VisualError("Shape contains unsafe style metadata")
    pairs = dict(part.split("=", 1) for part in style.split(";") if "=" in part)
    asset = pairs.pop("image", None)
    if asset is not None:
        # Official search absolutizes bundled icon paths for its browser preview.
        # Rebind only this exact built-in library prefix to desktop's offline assets.
        if asset.startswith("https://app.diagrams.net/"):
            asset = asset.removeprefix("https://app.diagrams.net/")
        asset = asset.removeprefix("/")
        if (".." in asset or not re.fullmatch(r"img/lib/[A-Za-z0-9_./-]+\.(?:svg|png)", asset)):
            raise VisualError("Shape requires external image assets; choose a bundled native draw.io icon")
        pairs["shape"] = "image"
    else:
        primitives = {"rectangle", "ellipse", "doubleEllipse", "rhombus", "process", "trapezoid"}
        shorthand = [part for part in style.split(";") if part and "=" not in part]
        if any(part not in primitives for part in shorthand) or not (pairs or shorthand):
            raise VisualError("Shape is not a bundled native draw.io stencil")
        # draw.io's Process style omits shape and uses the built-in rectangle.
        shape = pairs.get("shape", shorthand[0] if shorthand else "rectangle")
        if shape not in primitives and not re.fullmatch(r"mxgraph\.[A-Za-z0-9_.-]+", shape):
            raise VisualError("Shape is not a bundled native draw.io stencil")
        pairs["shape"] = shape
    allowed = {
        "shape", "resIcon", "prIcon", "fillColor", "strokeColor", "aspect", "pointerEvents",
        "gradientColor", "gradientDirection", "strokeWidth", "outlineConnect", "sketch",
        "verticalLabelPosition", "verticalAlign", "align", "rounded", "flipH", "flipV",
        "size", "arcSize", "absoluteArcSize", "dashed",
    }
    result = []
    for key, value in pairs.items():
        if key not in allowed:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_.#,-]+", value):
            raise VisualError("Shape contains unsupported style values")
        result.append(f"{key}={value}")
    if asset is not None:
        result.append(f"image={asset}")
    return ";".join(result) + ";"


@asynccontextmanager
async def _mcp_session(url: str):
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        raise VisualError("Diagram rendering requires the Python mcp SDK") from exc
    async with streamable_http_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


def _shapes(result: Any) -> list[dict[str, Any]]:
    if getattr(result, "isError", False):
        raise VisualError("draw.io MCP shape search failed")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and isinstance(structured.get("shapes"), list):
        return structured["shapes"]
    for block in getattr(result, "content", []):
        if getattr(block, "type", None) == "text":
            try:
                value = json.loads(block.text)
            except (ValueError, TypeError):
                continue
            if isinstance(value, list):
                return value
    raise VisualError("draw.io MCP returned no structured shape metadata")


def _kubernetes_resource(query: str) -> str | None:
    query = re.sub(r"([a-z])([A-Z])", r"\1 \2", query)
    words = re.findall(r"[a-z0-9]+", query.lower())
    if not set(words) & {"kubernetes", "k8s", "k8"} or set(words) & {
        "azure", "aws", "gcp", "google", "amazon", "microsoft", "alibaba",
    }:
        return None
    words = [word[:-1] if word.endswith("s") and word not in {"rs"} else word for word in words
             if word not in {"kubernetes", "k8s", "k8"} and not word.isdigit()]
    resource = "".join(words)
    return {"service": "svc", "deployment": "deploy", "replicaset": "rs",
            "pod": "pod", "svc": "svc", "deploy": "deploy", "rs": "rs"}.get(resource)


def _shape_candidates(query: str, shapes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def normalize(text: str) -> str:
        text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
        words = re.findall(r"[a-z0-9]+", text.lower())
        providers = {"azure", "aws", "gcp", "google", "amazon", "microsoft", "general", "generic", "flowchart"}
        return " ".join(word[:-1] if word.endswith("s") else word for word in words if word not in providers)

    expected = normalize(query)
    kubernetes = _kubernetes_resource(query)

    def semantic_rank(shape: Any) -> int:
        if not isinstance(shape, dict):
            return 3
        if kubernetes is None:
            return 0
        pairs = dict(part.split("=", 1) for part in str(shape.get("style", "")).split(";") if "=" in part)
        if pairs.get("shape", "").startswith("mxgraph.kubernetes.") and pairs.get("prIcon") == kubernetes:
            return 0
        return 1 if normalize(str(shape.get("title", ""))) == expected else 2

    # The upstream phonetic search can rank SQL DataWarehouse above SQL
    # Database. Prefer an exact normalized title, and current bundled artwork.
    # A requested resource must not silently become an unrelated cloud
    # container group merely because the phonetic search ranked it first.
    if kubernetes is not None:
        shapes = [shape for shape in shapes if semantic_rank(shape) == 0]
    return sorted(shapes, key=lambda shape: (
        semantic_rank(shape),
        normalize(str(shape.get("title", ""))) != expected if isinstance(shape, dict) else True,
        "img/lib/azure2/" not in str(shape.get("style", "")) if isinstance(shape, dict) else True,
    ))


def _diagram_xml(scene: EducationalScene, styles: list[str], width: int, height: int,
                 visible: int | None = None) -> str:
    diagram = scene.diagram
    if diagram is None:
        raise VisualError("Technical diagram scene has no structured nodes")
    count = len(diagram.nodes) if visible is None else visible
    columns = min(4, len(diagram.nodes))
    rows = math.ceil(len(diagram.nodes) / columns)
    positions = {node.id: (index % columns, index // columns)
                 for index, node in enumerate(diagram.nodes)}
    indegree = {node.id: 0 for node in diagram.nodes}
    children = {node.id: [] for node in diagram.nodes}
    levels = {node.id: 0 for node in diagram.nodes}
    for edge in diagram.edges:
        indegree[edge.target] += 1
        children[edge.source].append(edge.target)
    ready = [node.id for node in diagram.nodes if indegree[node.id] == 0]
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for target in children[current]:
            levels[target] = max(levels[target], levels[current] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited == len(diagram.nodes):
        tiers = [[node.id for node in diagram.nodes if levels[node.id] == level]
                 for level in range(max(levels.values()) + 1)]
        if len(tiers) <= 4 and max(map(len, tiers)) <= 4:
            columns, rows = len(tiers), max(map(len, tiers))
            # Forks place independent consumers in distinct rows, rather than
            # drawing a nonadjacent edge straight through an intervening icon.
            positions = {node_id: (column, index + (rows - len(tier)) / 2)
                         for column, tier in enumerate(tiers) for index, node_id in enumerate(tier)}
    # Label size follows the canvas and graph density, with a bounded two-line label.
    cell_w = (width - width * 0.08) / columns
    cell_h = (height - height * 0.16) / rows
    font = max(10, min(round(36 * height / 1080), int(min(cell_w / 15, cell_h / 9))))
    graph = ET.Element("mxGraphModel", grid="0", page="0", background="#ffffff")
    root = ET.SubElement(graph, "root")
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    background = ET.SubElement(root, "mxCell", id="canvas", value="", vertex="1", parent="1",
                               style="html=0;fillColor=#ffffff;strokeColor=none;")
    ET.SubElement(background, "mxGeometry", x="0", y="0", width=str(width), height=str(height),
                  **{"as": "geometry"})
    ids = {node.id for node in diagram.nodes[:count]}
    icon_sizes = {}
    icon_boxes = {}
    for index, node in enumerate(diagram.nodes[:count]):
        column, row = positions[node.id]
        x = width * 0.04 + column * cell_w
        y = height * 0.08 + row * cell_h
        icon_side = min(cell_w * 0.38, cell_h * 0.42)
        icon_sizes[node.id] = icon_side
        icon_boxes[node.id] = (x + (cell_w - icon_side) / 2, y, icon_side)
        icon = ET.SubElement(root, "mxCell", id=f"node-{node.id}", value="", vertex="1", parent="1",
                             style=styles[index] + "html=0;")
        ET.SubElement(icon, "mxGeometry", x=str(x + (cell_w - icon_side) / 2), y=str(y),
                      width=str(icon_side), height=str(icon_side), **{"as": "geometry"})
        label = ET.SubElement(
            root, "mxCell", id=f"label-{node.id}", value=node.label, vertex="1", parent="1",
            style=f"text;html=0;whiteSpace=wrap;align=center;verticalAlign=top;fontFamily=DejaVu Sans;"
                  f"fontSize={font};fontColor=#172b4d;overflow=hidden;",
        )
        ET.SubElement(label, "mxGeometry", x=str(x + cell_w * 0.04), y=str(y + icon_side + font * 0.4),
                      width=str(cell_w * 0.92), height=str(font * 4), **{"as": "geometry"})
    outgoing = {node.id: [] for node in diagram.nodes}
    incoming = {node.id: [] for node in diagram.nodes}
    for index, edge in enumerate(diagram.edges):
        outgoing[edge.source].append(index)
        incoming[edge.target].append(index)
    source_lanes = {}
    for node in diagram.nodes:
        if outgoing[node.id]:
            column = positions[node.id][0]
            source_lanes.setdefault(column, []).append(node.id)
    branches = [node.id for node in diagram.nodes if len(outgoing[node.id]) > 1]

    def port(indices: list[int], index: int) -> float:
        return 0.5 if len(indices) == 1 else 0.2 + 0.6 * indices.index(index) / (len(indices) - 1)

    for index, edge in enumerate(diagram.edges):
        if edge.source not in ids or edge.target not in ids:
            continue
        source_port, target_port = port(outgoing[edge.source], index), port(incoming[edge.target], index)
        source_rank = source_lanes[positions[edge.source][0]].index(edge.source)
        edge_font = max(10, min(round(24 * height / 1080), font - max(3, round(3 * height / 1080))))
        if len(incoming[edge.target]) > 1:
            separation = icon_sizes[edge.target] * 0.6 / (len(incoming[edge.target]) - 1)
            edge_font = max(10, min(edge_font, int(separation * 0.7)))
        source_x, _, source_size = icon_boxes[edge.source]
        target_x, target_y, target_size = icon_boxes[edge.target]
        gap = target_x - source_x - source_size
        caption_width = max(32, gap / 2 - (len(source_lanes[positions[edge.source][0]]) - 1) * font
                            - max(8, round(24 * height / 1080)) / 2)
        caption = bool(edge.label) and gap > 0
        if caption:
            edge_font = max(10, min(edge_font, int((caption_width - 8) / max(1, len(edge.label) * 0.56))))
        branch = edge.source if edge.source in branches else edge.target if edge.target in branches else None
        color = ("#0f766e", "#2563eb", "#7c3aed", "#b45309")[branches.index(branch) % 4] if branch else "#456789"
        dashed = color == "#2563eb" and re.search(
            r"\b(?:blue\s+dashed|dashed\s+blue)\b", f"{scene.description} {scene.image_prompt}", re.I,
        )
        cell = ET.SubElement(
            root, "mxCell", id=f"edge-{index}", value=edge.label, edge="1", parent="1",
            source=f"node-{edge.source}", target=f"node-{edge.target}",
            style=f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=0;endArrow=classic;"
                  f"exitX=1;exitY={source_port:g};entryX=0;entryY={target_port:g};"
                  f"sourceJettySize={max(8, round(24 * height / 1080)) + source_rank * font * 2};"
                  f"targetJettySize={max(8, round(24 * height / 1080))};"
                  f"labelBackgroundColor=#ffffff;fontColor={color};"
                  f"fontFamily=DejaVu Sans;fontSize={edge_font};strokeColor={color};strokeWidth=2;"
                  f"dashed={int(bool(dashed))};noLabel={int(caption)};",
        )
        # Icons have separate labels below them: side connections avoid those
        # labels; destination-biased edge text separates shared fork trunks.
        ET.SubElement(cell, "mxGeometry", x="0.6", y=str(-edge_font * 0.65), relative="1", **{"as": "geometry"})
        if caption:
            # Arc-length label positions differ on long/short fan-in routes.
            # Use disjoint destination-port bands, outside all source buses.
            label = ET.SubElement(
                root, "mxCell", id=f"edge-label-{index}", value=edge.label, vertex="1", parent="1",
                style=f"text;html=0;align=center;verticalAlign=top;whiteSpace=wrap;"
                      f"fontFamily=DejaVu Sans;fontSize={edge_font};fontColor={color};"
                      f"fillColor=#ffffff;strokeColor=none;overflow=hidden;",
            )
            ET.SubElement(
                label, "mxGeometry", x=str(target_x - caption_width), y=str(target_y + target_size * target_port + 4),
                width=str(caption_width - 8), height=str(edge_font * 1.25 + 4), **{"as": "geometry"},
            )
    return ET.tostring(graph, encoding="unicode")


class EducationalVisuals:
    def __init__(self, settings: Settings, comfy: ComfyUIPool, credential: Any):
        self.settings = settings
        self.comfy = comfy
        self.credential = credential
        self.http = httpx.AsyncClient(timeout=180, follow_redirects=False)
        self._shape_cache: dict[str, str] = {}
        self._ffmpeg_slots = asyncio.Semaphore(max(1, settings.ffmpeg_concurrency))

    async def aclose(self) -> None:
        """Close owned HTTP resources; the shared pool/credential remain caller-owned."""
        await self.http.aclose()

    @staticmethod
    def companion_assets(image: Path, scene: EducationalScene) -> dict[str, Path]:
        """Stable persistence keys/paths for a diagram's generated companions."""
        if scene.diagram is None:
            return {}
        assets = {"diagram_xml": image.with_suffix(".drawio")}
        if scene.animation == "reveal":
            assets.update({
                f"reveal_{i:02d}": image.with_name(f"{image.stem}.reveal-{i:02d}.png")
                for i in range(1, len(scene.diagram.nodes) + 1)
            })
        return assets

    async def restore_reveals(self, image: Path, scene: EducationalScene, width: int, height: int) -> None:
        """Rebuild missing reveal rasters from persisted .drawio, without MCP/GPU calls.

        Only styles for this approved structured graph are recovered. Untrusted
        XML is never handed to the exporter; a fresh constrained model is built.
        Persisting image + diagram_xml is sufficient for restart recovery.
        """
        _canvas(width, height)
        if scene.diagram is None or scene.animation != "reveal":
            return
        assets = self.companion_assets(image, scene)
        stages = [path for key, path in assets.items() if key.startswith("reveal_")]
        missing = [path for path in stages if not _io_path(path).is_file()]
        if not missing:
            return
        editable = assets["diagram_xml"]
        if not _io_path(editable).is_file() or _io_path(editable).stat().st_size > 1_000_000:
            raise VisualError("Reveal recovery requires the persisted bounded diagram_xml .drawio artifact")
        try:
            xml = _io_path(editable).read_text(encoding="utf-8")
            if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
                raise VisualError("Stored diagram contains prohibited XML declarations")
            graph = ET.fromstring(xml)
            if graph.tag != "mxGraphModel":
                raise VisualError("Stored diagram must be an uncompressed generated mxGraphModel")
            styles = []
            for node in scene.diagram.nodes:
                icon = graph.find(f"./root/mxCell[@id='node-{node.id}']")
                label = graph.find(f"./root/mxCell[@id='label-{node.id}']")
                if icon is None or label is None or label.get("value") != node.label:
                    raise VisualError("Stored diagram differs from the approved scene; regenerate the diagram")
                styles.append(_native_style(icon.get("style")))
        except (OSError, ValueError, ET.ParseError) as exc:
            raise VisualError("Persisted diagram could not be safely recovered") from exc
        async with asyncio.timeout(600):
            for count, stage in enumerate(stages, 1):
                if _io_path(stage).is_file():
                    continue
                with _temporary_diagram(stage.parent, _diagram_xml(scene, styles, width, height, count)) as stage_xml:
                    await self._export(stage_xml, stage, width, height)

    async def image(self, scene: EducationalScene, width: int, height: int, seed: int,
                    dest: Path, resume: dict | None = None,
                    on_submitted: SubmittedCallback | None = None, *,
                    provider: str = "comfyui") -> Path:
        """Generate a sufficient-resolution illustration without silent enhancement.

        Foundry GPT-image has no seed or asynchronous submission ID: seed and
        on_submitted apply only to ComfyUI. Foundry resume explicitly fails.
        """
        _canvas(width, height)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if scene.diagram is not None:
            raise VisualError("Render technical diagrams with diagram(), not a generative image provider")
        if provider == "comfyui":
            configured = self.settings.comfy_image_workflow
            template_path = Path(configured) if configured else None
            if template_path is None or not template_path.is_file():
                raise VisualError("Set COMFY_IMAGE_WORKFLOW to a verified ComfyUI T2I API JSON template")
            try:
                template = load_workflow(template_path)
            except (OSError, ValueError) as exc:
                raise VisualError("COMFY_IMAGE_WORKFLOW is not readable valid JSON") from exc
            if not isinstance(template, dict) or not template or not all(
                isinstance(n, dict) and isinstance(n.get("inputs"), dict) for n in template.values()
            ):
                raise VisualError("COMFY_IMAGE_WORKFLOW must be API node JSON, not editor workflow JSON")
            placeholders = {v for n in template.values() for v in n.get("inputs", {}).values()
                            if isinstance(v, str) and v.startswith("{{")}
            required = {"{{prompt}}", "{{width}}", "{{height}}", "{{seed}}", "{{filename_prefix}}"}
            if not required <= placeholders or "{{image}}" in placeholders:
                raise VisualError("T2I template requires prompt,width,height,seed,filename_prefix placeholders; no image")
            render_width, render_height = width, height
            if template_path.resolve() == QWEN_T2I_WORKFLOW.resolve():
                # EmptySD3LatentImage/Qwen patch alignment: round up, never reduce
                # the requested raster below the final canvas (1080 becomes 1088).
                render_width, render_height = math.ceil(width / 16) * 16, math.ceil(height / 16) * 16
            params = {"prompt": scene.image_prompt, "negative_prompt": "",
                      "width": render_width, "height": render_height,
                      "filename_prefix": f"education/{dest.stem}"}
            fill_workflow(template, dict(params, seed=seed))
            await self.comfy._render(
                template_path, params, seed, dest, self.settings.clip_timeout_seconds,
                self.settings.clip_retries, resume, on_submitted, IMAGE_EXTENSIONS, None,
                "education", "Educational illustration",
            )
        elif provider == "foundry":
            if resume:
                raise VisualError("Foundry synchronous image generation cannot reattach; no exactly-once billing guarantee")
            endpoint = _endpoint(self.settings.foundry_image_endpoint, "FOUNDRY_IMAGE_ENDPOINT")
            deployment = self.settings.foundry_image_model
            if not deployment:
                raise VisualError("Set FOUNDRY_IMAGE_MODEL to an existing GPT-image deployment")
            options = [(1024, 1024), (1536, 1024), (1024, 1536)]
            candidates = [size for size in options if size[0] >= width and size[1] >= height]
            if not candidates:
                raise VisualError("GPT-image supports at most 1536x1024 / 1024x1536; select explicit upscaling")
            selected = min(candidates, key=lambda size: size[0] * size[1])
            response = await self.http.post(
                f"{endpoint}/openai/deployments/{quote(deployment, safe='')}/images/generations",
                params={"api-version": "2025-04-01-preview"},
                headers=await self._headers("https://cognitiveservices.azure.com/.default"),
                json={"prompt": scene.image_prompt, "n": 1, "size": f"{selected[0]}x{selected[1]}",
                      "quality": "high", "output_format": "png"},
            )
            response.raise_for_status()
            try:
                data = base64.b64decode(response.json()["data"][0]["b64_json"], validate=True)
                with Image.open(BytesIO(data)) as im:
                    if im.width * im.height > 50_000_000:
                        raise VisualError("Foundry image exceeds the 50 million pixel decoding limit")
                    im.load()
                    if im.width < width or im.height < height:
                        raise VisualError("Foundry returned an undersized image; explicit upscaling required")
                    output = BytesIO()
                    im.convert("RGB").save(output, "PNG")
                _atomic_bytes(dest, output.getvalue())
            except (KeyError, IndexError, TypeError, ValueError, OSError, binascii.Error) as exc:
                raise VisualError("Foundry returned no valid base64 raster image") from exc
        else:
            raise VisualError(f"Unsupported image provider: {provider}")
        try:
            _sufficient(dest, width, height)
        except VisualError:
            dest.unlink(missing_ok=True)
            raise
        return dest

    async def _headers(self, scope: str) -> dict[str, str]:
        if self.credential is None:
            raise VisualError("Foundry visual generation requires an async Azure token credential")
        token = await self.credential.get_token(scope)
        return {"Authorization": f"Bearer {token.token}"}

    async def diagram(self, scene: EducationalScene, width: int, height: int, dest: Path) -> Path:
        _canvas(width, height)
        if scene.diagram is None:
            raise VisualError("diagram() requires structured TechnicalDiagram nodes/edges")
        url = self.settings.drawio_mcp_url
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise VisualError("Set DRAWIO_MCP_URL to a private self-hosted Streamable HTTP /mcp endpoint")
        if parsed.hostname.lower() in {"mcp.draw.io", "app.diagrams.net", "viewer.diagrams.net"}:
            raise VisualError("Public draw.io endpoints are not permitted; configure a private self-hosted MCP")
        _command(self.settings.drawio_export_command)
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with asyncio.timeout(120):
            async with _mcp_session(url) as session:
                styles = []
                for node in scene.diagram.nodes:
                    resource = _kubernetes_resource(node.icon_query)
                    query = f"Kubernetes {resource}" if resource else node.icon_query
                    cache_key = f"semantic-v3:{query}"
                    if cache_key not in self._shape_cache:
                        response = await session.call_tool("search_shapes", {"query": query, "limit": 10})
                        style = None
                        for candidate in _shape_candidates(node.icon_query, _shapes(response)):
                            try:
                                style = _native_style(candidate.get("style"))
                                break
                            except (VisualError, AttributeError):
                                continue
                        if style is None:
                            raise VisualError(f"No safe bundled native shape for {node.icon_query!r}; revise icon_query")
                        self._shape_cache[cache_key] = style
                    styles.append(self._shape_cache[cache_key])
                xml = _diagram_xml(scene, styles, width, height)
                created = await session.call_tool("create_diagram", {"xml": xml})
                if getattr(created, "isError", False):
                    raise VisualError("draw.io MCP create_diagram rejected the structured diagram")
                # MCP preview/layout output is client-side. Export our deterministic XML, not a UI link.
        editable = dest.with_suffix(".drawio")
        _atomic_bytes(editable, xml.encode("utf-8"))
        if scene.animation == "reveal":
            for count in range(1, len(scene.diagram.nodes) + 1):
                stage = dest.with_name(f"{dest.stem}.reveal-{count:02d}.png")
                with _temporary_diagram(stage.parent, _diagram_xml(scene, styles, width, height, count)) as stage_xml:
                    await self._export(stage_xml, stage, width, height)
        await self._export(editable, dest, width, height)
        return dest

    async def _export(self, editable: Path, dest: Path, width: int, height: int) -> None:
        pending = dest.with_name(f".{uuid.uuid4().hex}.png")
        io_pending = _io_path(pending)
        try:
            await _run(_command(self.settings.drawio_export_command) + [
                "--export", "--format", "png", "--output", str(pending.resolve()),
                "--width", str(width), "--height", str(height), "--border", "0", str(editable.resolve()),
            ], timeout=120)
            if not io_pending.is_file():
                raise VisualError("draw.io export produced no PNG (MCP previews are not raster exports)")
            with Image.open(io_pending) as im:
                im.load()
                if im.width > width or im.height > height or im.width < width - 2 or im.height < height - 2:
                    raise VisualError(f"draw.io export canvas mismatch: {im.width}x{im.height}, expected {width}x{height}")
                canvas = Image.new("RGB", (width, height), "white")
                rgba = im.convert("RGBA")
                canvas.paste(rgba, ((width - im.width) // 2, (height - im.height) // 2), rgba)
                canvas.save(io_pending, "PNG")
            io_pending.replace(_io_path(dest))
        finally:
            io_pending.unlink(missing_ok=True)

    async def motion(self, image: Path, prompt: str, model: VideoModel, seed: int, dest: Path,
                     provider: str = "comfyui", resume: dict | None = None,
                     on_submitted: SubmittedCallback | None = None, *,
                     width: int | None = None, height: int | None = None,
                     upload_subfolder: str | None = None) -> Path:
        """Animate an illustration, not a diagram or its exact technical labels.

        Foundry uses the configured deployment, model's dimensions, and rounded-up
        clip seconds; its preview API has no seed control. Native dimensions are
        orientation-swapped for portrait images unless both overrides are supplied.
        Callers must probe/trim
        provider clips, and explicitly upscale if the final canvas is larger.
        """
        dest.parent.mkdir(parents=True, exist_ok=True)
        source_width, source_height = _size(image)
        if (width is None) != (height is None):
            raise VisualError("Motion width and height overrides must be supplied together")
        render_width, render_height = (
            (width, height) if width is not None else model.render_size(
                "vertical" if source_height > source_width else "horizontal"
            )
        )
        _canvas(render_width, render_height)
        if provider == "comfyui":
            namespace = upload_subfolder
            if namespace is None:
                with image.open("rb") as source:
                    content_hash = hashlib.file_digest(source, "sha256").hexdigest()[:16]
                destination_hash = hashlib.sha256(str(dest.resolve()).encode("utf-8")).hexdigest()[:16]
                namespace = f"education/{content_hash}-{destination_hash}"
            if not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", namespace):
                raise VisualError("Motion upload_subfolder must be a safe job-scoped relative namespace")
            await self.comfy.generate_clip(
                model, prompt, seed, dest, f"{namespace}/{dest.stem}", self.settings.clip_timeout_seconds,
                self.settings.clip_retries, resume=resume, on_submitted=on_submitted, start_image=image,
                upload_subfolder=namespace, width=render_width, height=render_height,
            )
            return dest
        if provider != "foundry":
            raise VisualError(f"Unsupported motion provider: {provider}")
        endpoint = _endpoint(self.settings.foundry_video_endpoint, "FOUNDRY_VIDEO_ENDPOINT")
        deployment = self.settings.foundry_video_model
        if not deployment:
            raise VisualError("Set FOUNDRY_VIDEO_MODEL to a deployment supporting Azure preview I2V jobs")
        if resume and (resume.get("server") != endpoint or not resume.get("prompt_id")):
            raise VisualError("Foundry resume metadata must match this endpoint and include prompt_id")
        job_id = resume["prompt_id"] if resume else None
        if job_id is not None and not isinstance(job_id, str):
            raise VisualError("Foundry resume prompt_id must be a string")
        if job_id is None:
            seconds = math.ceil(model.clip_seconds)
            if not 1 <= seconds <= 20:
                raise VisualError("Azure preview video adapter supports a bounded 1–20 second clip request")
            fields = {"prompt": prompt, "width": str(render_width), "height": str(render_height),
                      "n_seconds": str(seconds), "n_variants": "1", "model": deployment,
                      "inpaint_items": json.dumps([{"frame_index": 0, "type": "image", "file_name": "input.png"}])}
            with Image.open(image) as source:
                buffer = BytesIO()
                source.convert("RGB").save(buffer, "PNG")
            response = await self.http.post(
                f"{endpoint}/openai/v1/video/generations/jobs", params={"api-version": "preview"},
                headers=await self._headers("https://ai.azure.com/.default"), data=fields,
                files={"files": ("input.png", buffer.getvalue(), "image/png")},
            )
            if response.status_code in {400, 403, 404, 422}:
                raise VisualError(
                    f"Foundry preview I2V unavailable for this deployment/resource/region or dimensions "
                    f"(HTTP {response.status_code}); configure a verified I2V deployment. No chat fallback."
                )
            response.raise_for_status()
            job_id = response.json().get("id")
            if not isinstance(job_id, str) or not job_id:
                raise VisualError("Foundry I2V returned no job ID; submission cannot be safely retried")
            if on_submitted:
                await on_submitted(endpoint, job_id)
        async with asyncio.timeout(self.settings.clip_timeout_seconds):
            while True:
                response = await self.http.get(
                    f"{endpoint}/openai/v1/video/generations/jobs/{quote(job_id, safe='')}",
                    params={"api-version": "preview"},
                    headers=await self._headers("https://ai.azure.com/.default"),
                )
                response.raise_for_status()
                status = response.json()
                if status.get("status") == "succeeded":
                    break
                if status.get("status") in {"failed", "cancelled"}:
                    raise VisualError(f"Foundry I2V job {job_id} {status['status']}; inspect provider diagnostics")
                if status.get("status") not in {"queued", "pending", "running", "processing", "in_progress"}:
                    raise VisualError(f"Foundry I2V job returned unknown status: {status.get('status')!r}")
                await asyncio.sleep(3)
            generations = status.get("generations", [])
            if (not isinstance(generations, list) or not generations
                    or not isinstance(generations[0], dict)
                    or not isinstance(generations[0].get("id"), str) or not generations[0]["id"]):
                raise VisualError("Foundry I2V succeeded without a video generation ID")
            response = await self.http.get(
                f"{endpoint}/openai/v1/video/generations/{quote(generations[0]['id'], safe='')}/content/video",
                params={"api-version": "preview"}, headers=await self._headers("https://ai.azure.com/.default"),
            )
            response.raise_for_status()
            if not response.content:
                raise VisualError("Foundry I2V returned empty video content")
            _atomic_bytes(dest, response.content)
        return dest

    async def animate(self, image: Path, scene: EducationalScene, seconds: float, width: int,
                      height: int, fps: int, dest: Path) -> Path:
        _canvas(width, height)
        if not math.isfinite(seconds) or not 0 < seconds <= 600 or not 1 <= fps <= 60:
            raise VisualError("Animation requires 0–600 seconds and 1–60 fps")
        if width % 2 or height % 2:
            raise VisualError("H.264 presentation canvas dimensions must be even")
        _sufficient(image, width, height)
        font = Path(self.settings.education_font) if self.settings.education_font else None
        if font is None or not font.is_file():
            raise VisualError("Set EDUCATION_FONT to a locally installed readable TrueType/OpenType font")
        dest.parent.mkdir(parents=True, exist_ok=True)
        folder = dest.parent.resolve()
        tag = uuid.uuid4().hex
        textfile, fontfile = folder / f".title-{tag}.txt", folder / f".font-{tag}{font.suffix}"
        pending = folder / f".animation-{tag}.mp4"
        manifest = folder / f".reveal-{tag}.txt"
        staged_inputs: list[Path] = []
        frames = max(1, math.ceil(seconds * fps))
        duration = frames / fps
        fade = min(0.35, duration / 4)
        try:
            textfile.write_text(re.sub(r"[\x00-\x1f\x7f]", " ", scene.title), encoding="utf-8")
            shutil.copyfile(font, fontfile)
            args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
            diagram = scene.diagram is not None
            if diagram and scene.animation == "reveal":
                await self.restore_reveals(image, scene, width, height)
                paths = [image.with_name(f"{image.stem}.reveal-{i:02d}.png")
                         for i in range(1, len(scene.diagram.nodes) + 1)]
                # Keep paths out of ffmpeg's concat syntax; generated safe relative filenames only.
                lines = []
                for i, path in enumerate(paths):
                    if not path.is_file() or _size(path) != (width, height):
                        raise VisualError("Diagram reveal requires exact-canvas PNG stages from diagram()")
                    stage = folder / f"stage-{tag}-{i:02d}.png"
                    shutil.copyfile(path, stage)
                    staged_inputs.append(stage)
                    lines.extend([f"file '{stage.name}'", f"duration {duration / len(paths):.9f}"])
                lines.append(f"file '{staged_inputs[-1].name}'")
                manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
                args += ["-f", "concat", "-safe", "1", "-i", manifest.name]
                visual = f"fps={fps},scale={width}:{height}"
            else:
                args += ["-loop", "1", "-framerate", str(fps), "-i", str(image.resolve())]
                visual = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
                if not diagram and scene.animation in {"zoom_in", "zoom_out", "pan"}:
                    progress = f"on/{max(1, frames - 1)}"
                    zoom = f"1+0.06*{progress}" if scene.animation == "zoom_in" else (
                        f"1.06-0.06*{progress}" if scene.animation == "zoom_out" else "1.06")
                    x = f"(iw-iw/zoom)*{progress}" if scene.animation == "pan" else "iw/2-iw/zoom/2"
                    visual += f",zoompan=z='{zoom}':x='{x}':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps}"
            title_size = max(12, min(60, height // 22, width // max(10, len(scene.title))))
            filters = (
                f"{visual},drawtext=fontfile={fontfile.name}:textfile={textfile.name}:expansion=none:"
                f"fontsize={title_size}:fontcolor=white:box=1:boxcolor=0x172b4d@0.88:boxborderw=8:"
                f"x=(w-text_w)/2:y=h-text_h-24,"
                f"fade=t=in:st=0:d={fade:.6f},fade=t=out:st={duration-fade:.6f}:d={fade:.6f},format=yuv420p"
            )
            args += ["-vf", filters, "-frames:v", str(frames), "-r", str(fps), "-an", "-c:v", "libx264",
                     "-threads", "2", "-preset", "medium", "-crf", "18", "-movflags", "+faststart", pending.name]
            async with self._ffmpeg_slots:
                await _run(args, cwd=folder)
            if not pending.is_file() or pending.stat().st_size == 0:
                raise VisualError("ffmpeg produced no presentation video")
            pending.replace(dest.resolve())
        finally:
            for path in [textfile, fontfile, pending, manifest, *staged_inputs]:
                path.unlink(missing_ok=True)
        return dest
