"""Explicit live, private draw.io + PNG + deterministic reveal smoke test.

Does not provision/start a GPU, call image/video models, or use hosted MCP.
The caller starts its own private pinned service/exporter before running this.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from video_platform.comfyui import ComfyUIPool
from video_platform.config import Settings
from video_platform.education_schemas import EducationalScene, TechnicalDiagram
from video_platform.education_visuals import EducationalVisuals, _native_style


async def run(args: argparse.Namespace) -> None:
    args.output.mkdir(parents=True, exist_ok=True)
    scene = EducationalScene(
        title="Application architecture",
        description="A deterministic native-icon architecture smoke test.",
        narration="The application runs on Kubernetes and uses a SQL database and object storage.",
        image_prompt="Not used: technical labels and icons are deterministic.",
        source_ids=["s1"], animation="reveal",
        diagram=TechnicalDiagram(
            nodes=[
                {"id": "aks", "label": "Kubernetes application", "icon_query": "Azure Kubernetes Services"},
                {"id": "sql", "label": "SQL database", "icon_query": "Azure SQL Database"},
                {"id": "blob", "label": "Object storage", "icon_query": "Azure Storage Account"},
            ],
            edges=[
                {"source": "aks", "target": "sql", "label": "queries"},
                {"source": "aks", "target": "blob", "label": "stores"},
            ],
        ),
    )
    if args.scene:
        scene = EducationalScene.model_validate_json(args.scene.read_text(encoding="utf-8"))
    settings = Settings(
        drawio_mcp_url=args.mcp_url, drawio_export_command=args.export_command,
        education_font=str(args.font), ffmpeg_concurrency=1,
    )
    # Pool is caller-owned but deliberately unreachable: this test never renders
    # generative images/motion or contacts a GPU.
    pool = ComfyUIPool.from_urls(["http://127.0.0.1:9"])
    visuals = EducationalVisuals(settings, pool, None)
    image = args.output / "architecture.png"
    video = args.output / "architecture-reveal.mp4"
    try:
        await visuals.diagram(scene, args.width, args.height, image)
        companions = visuals.companion_assets(image, scene)
        graph = ET.fromstring(companions["diagram_xml"].read_text(encoding="utf-8"))
        styles = {
            node.id: graph.find(f"./root/mxCell[@id='node-{node.id}']").get("style")
            for node in scene.diagram.nodes
        }
        edges = graph.findall("./root/mxCell[@edge='1']")
        assert [(edge.get("source"), edge.get("target"), edge.get("value")) for edge in edges] == [
            (f"node-{edge.source}", f"node-{edge.target}", edge.label or "") for edge in scene.diagram.edges
        ]
        for style in styles.values():
            assert "http:" not in style and "https:" not in style
            assert _native_style(style)
        raster_paths = [image] + [path for key, path in companions.items() if key.startswith("reveal_")]
        for path in raster_paths:
            with Image.open(path) as raster:
                assert raster.size == (args.width, args.height), (path, raster.size)
                rgb = raster.convert("RGB")
                assert ImageChops.difference(rgb, Image.new("RGB", rgb.size, "white")).getbbox()
        icon_pixels = {}
        with Image.open(image) as raster:
            rgb = raster.convert("RGB")
            for node in scene.diagram.nodes:
                geometry = graph.find(f"./root/mxCell[@id='node-{node.id}']/mxGeometry")
                x, y, width, height = (float(geometry.get(key)) for key in ("x", "y", "width", "height"))
                crop = rgb.crop((int(x), int(y), int(x + width), int(y + height)))
                count = sum(max(pixel) - min(pixel) > 30 for pixel in crop.get_flattened_data())
                visible = sum(min(pixel) < 220 for pixel in crop.get_flattened_data())
                assert visible > 20, f"{node.id}: native icon did not rasterize visibly"
                icon_pixels[node.id] = count
        await visuals.animate(image, scene, 1, args.width, args.height, 24, video)
        metadata = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video),
        ]))
        stream = metadata["streams"][0]
        assert (stream["width"], stream["height"], stream["nb_frames"]) == (args.width, args.height, "24")
        scene_path = args.output / "architecture.scene.json"
        scene_path.write_text(scene.model_dump_json(indent=2), encoding="utf-8")
        report = {
            "mcp_url": args.mcp_url, "export_command": args.export_command,
            "image": str(image.resolve()), "video": str(video.resolve()),
            "companions": {key: str(path.resolve()) for key, path in companions.items()},
            "scene": str(scene_path.resolve()), "native_styles": styles, "colored_icon_pixels": icon_pixels,
            "png_dimensions": [args.width, args.height], "video_frames": 24,
            "live_image_or_video_generation": False,
        }
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        await visuals.aclose()
        await pool.aclose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mcp-url", required=True)
    parser.add_argument("--export-command", required=True)
    parser.add_argument("--font", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / ".live_validation")
    parser.add_argument("--scene", type=Path)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
