"""Verify CUDA 13 device reporting and two uncached ComfyUI API generations."""

import argparse
import copy
import hashlib
import json
import struct
import time
import uuid
import zlib
from pathlib import Path
from urllib import error, parse, request


def require_cuda13(stats):
    system = stats.get("system", {})
    version = system.get("pytorch_version", "")
    devices = stats.get("devices", [])
    if not isinstance(version, str) or "+cu130" not in version:
        raise RuntimeError(f"Expected PyTorch cu130 build, received {version!r}")
    if not any(
        d.get("type") == "cuda" and "A100" in d.get("name", "")
        for d in devices
    ):
        raise RuntimeError(f"Expected an A100 CUDA device, received {devices!r}")


class ComfyUIClient:
    def __init__(self, base_url, request_timeout=120):
        parsed = parse.urlsplit(base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("An explicit HTTPS ComfyUI endpoint is required")
        self.base_url = base_url.rstrip("/")
        self.request_timeout = request_timeout

    def get_bytes(self, path, query=None, body=None, timeout=None):
        deadline = time.monotonic() + (timeout or self.request_timeout)
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Request deadline exceeded: {path}")
            try:
                return self._get_bytes(path, query, body, remaining if path == "/view" else min(30, remaining))
            except error.HTTPError:
                raise
            except (error.URLError, TimeoutError, ConnectionError) as exc:
                # Retrying a POST could queue duplicate inference; retry only reads.
                if body is not None or attempt == 2:
                    raise
                print(f"Retrying GET {path} after transport failure: {exc}", flush=True)
                time.sleep(min(1, max(0, deadline - time.monotonic())))

    def _get_bytes(self, path, query, body, timeout):
        url = f"{self.base_url}{path}"
        if query:
            url += "?" + parse.urlencode(query)
        data = None if body is None else json.dumps(body).encode()
        req = request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with request.urlopen(req, timeout=timeout or self.request_timeout) as response:
            if parse.urlsplit(response.url).scheme != "https":
                raise RuntimeError("ComfyUI redirected to an insecure endpoint")
            return response.read()

    def json(self, path, **kwargs):
        payload = json.loads(self.get_bytes(path, **kwargs))
        if not isinstance(payload, dict):
            raise RuntimeError(f"Expected a JSON object from {path}")
        return payload

    def ready(self, timeout):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ComfyUI cold-start readiness timed out")
            try:
                stats = self.json("/system_stats", timeout=min(self.request_timeout, remaining))
            except error.HTTPError as exc:
                if exc.code not in (502, 503, 504):
                    raise
                print(f"Cold start: HTTP {exc.code}", flush=True)
            except (error.URLError, TimeoutError) as exc:
                print(f"Cold start: {exc}", flush=True)
            else:
                require_cuda13(stats)
                return stats
            time.sleep(min(2, max(0, deadline - time.monotonic())))

    def submit(self, workflow):
        result = self.json("/prompt", body={"prompt": workflow, "client_id": str(uuid.uuid4())})
        prompt_id = result.get("prompt_id")
        if result.get("error") or result.get("node_errors") or not isinstance(prompt_id, str) or not prompt_id:
            raise RuntimeError(f"Workflow submission failed: {result}")
        return prompt_id

    def wait(self, prompt_id, save_node, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            history = self.json(
                f"/history/{parse.quote(prompt_id, safe='')}",
                timeout=min(self.request_timeout, deadline - time.monotonic()),
            ).get(prompt_id)
            if history is not None:
                if not isinstance(history, dict) or not isinstance(history.get("status"), dict):
                    raise RuntimeError(f"Malformed history for {prompt_id}: {history}")
                status = history["status"]
                messages = status.get("messages", [])
                if status.get("status_str") == "error" or any(
                    message[0] in ("execution_error", "execution_interrupted")
                    for message in messages
                ):
                    raise RuntimeError(f"ComfyUI execution failed for {prompt_id}: {status}")
                if status.get("completed"):
                    if status.get("status_str") != "success":
                        raise RuntimeError(f"Unsuccessful completion for {prompt_id}: {status}")
                    images = history.get("outputs", {}).get(save_node, {}).get("images", [])
                    if len(images) != 1 or not isinstance(images[0], dict):
                        raise RuntimeError(f"Expected one SaveImage output: {history}")
                    image = images[0]
                    if not image.get("filename") or image.get("type") != "output":
                        raise RuntimeError(f"Invalid output image: {image}")
                    return image
            time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise TimeoutError(f"Timed out waiting for prompt_id={prompt_id}")


def prepare_workflow(original, objects, seed, prefix):
    workflow = copy.deepcopy(original)
    save_nodes = []
    samplers = []
    latents = []
    for node_id, node in workflow.items():
        class_type = node["class_type"]
        if class_type not in objects:
            raise RuntimeError(f"Missing workflow node type: {class_type}")
        inputs = node["inputs"]
        required = objects[class_type]["input"]["required"]
        for key in ("unet_name", "clip_name", "vae_name", "sampler_name", "scheduler"):
            if key in inputs and inputs[key] not in required[key][0]:
                raise RuntimeError(f"Unavailable {key}: {inputs[key]}")
        if class_type == "KSampler":
            samplers.append(node_id)
            inputs.update(seed=seed, steps=8)
        elif class_type == "EmptySD3LatentImage":
            latents.append(node_id)
            inputs.update(width=1024, height=1024, batch_size=1)
        elif class_type == "SaveImage":
            save_nodes.append(node_id)
            inputs["filename_prefix"] = prefix
    if len(save_nodes) != 1 or len(samplers) != 1 or len(latents) != 1:
        raise RuntimeError("Expected one SaveImage, KSampler and EmptySD3LatentImage")
    return workflow, save_nodes[0]


def decode_png(data, expected_size=(1024, 1024)):
    """Decode non-interlaced 8-bit RGB/RGBA PNGs produced by ComfyUI."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Output is not PNG")
    offset = 8
    compressed = bytearray()
    header = None
    ended = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        end = offset + 8 + size
        if end + 4 > len(data):
            raise ValueError("Truncated PNG data")
        chunk = data[offset + 8:end]
        crc = struct.unpack_from(">I", data, end)[0]
        if zlib.crc32(kind + chunk) & 0xFFFFFFFF != crc:
            raise ValueError("Invalid PNG checksum")
        if header is None and kind != b"IHDR":
            raise ValueError("Missing PNG header")
        if kind == b"IHDR":
            if header is not None or len(chunk) != 13:
                raise ValueError("Invalid PNG header")
            header = struct.unpack(">IIBBBBB", chunk)
        elif kind == b"IDAT":
            compressed.extend(chunk)
        elif kind == b"IEND":
            if chunk or end + 4 != len(data):
                raise ValueError("Invalid PNG end")
            ended = True
            break
        offset = end + 4
    if not ended or header is None:
        raise ValueError("Incomplete PNG")
    width, height, depth, color, compression, filtering, interlace = header
    if (width, height) != expected_size:
        raise ValueError(f"Expected {expected_size}, received {(width, height)}")
    if depth != 8 or color not in (2, 6) or (compression, filtering, interlace) != (0, 0, 0):
        raise ValueError("Unsupported PNG encoding")
    channels = 3 if color == 2 else 4
    stride = width * channels
    expected_length = height * (stride + 1)
    inflater = zlib.decompressobj()
    raw = inflater.decompress(compressed, expected_length + 1)
    if len(raw) != expected_length or not inflater.eof or inflater.unused_data:
        raise ValueError("Invalid PNG pixel stream")
    previous = bytearray(stride)
    pixels = bytearray()
    for row_offset in range(0, len(raw), stride + 1):
        mode = raw[row_offset]
        if mode > 4:
            raise ValueError("Invalid PNG row filter")
        row = bytearray(raw[row_offset + 1:row_offset + 1 + stride])
        for i in range(stride):
            left = row[i - channels] if i >= channels else 0
            up = previous[i]
            upper_left = previous[i - channels] if i >= channels else 0
            if mode == 1:
                predictor = left
            elif mode == 2:
                predictor = up
            elif mode == 3:
                predictor = (left + up) // 2
            elif mode == 4:
                p = left + up - upper_left
                distances = (abs(p - left), abs(p - up), abs(p - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
            else:
                predictor = 0
            row[i] = (row[i] + predictor) & 255
        pixels.extend(row)
        previous = row
    return {"width": width, "height": height, "pixel_sha256": hashlib.sha256(pixels).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--workflow", type=Path, default=Path(__file__).with_name("image_z_image_turbo.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--startup-timeout", type=float, default=900)
    parser.add_argument("--execution-timeout", type=float, default=900)
    args = parser.parse_args()
    if args.startup_timeout <= 0 or args.execution_timeout <= 0:
        parser.error("Timeouts must be positive")
    client = ComfyUIClient(args.endpoint)
    stats = client.ready(args.startup_timeout)
    objects = client.json("/object_info")
    original = json.loads(args.workflow.read_text(encoding="utf-8"))
    run_id = uuid.uuid4().hex
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {"endpoint": args.endpoint, "system_stats": stats, "runs": []}
    for index, seed in enumerate((123456789, 123456790), start=1):
        workflow, save_node = prepare_workflow(original, objects, seed, f"cuda13-{run_id}-{index}")
        started = time.monotonic()
        prompt_id = client.submit(workflow)
        print(f"Submitted seed={seed}, prompt_id={prompt_id}", flush=True)
        image = client.wait(prompt_id, save_node, args.execution_timeout)
        data = client.get_bytes("/view", query=image, timeout=120)
        metadata = decode_png(data)
        path = output_dir / f"run-{index}.png"
        path.write_bytes(data)
        report["runs"].append({
            "prompt_id": prompt_id, "seed": seed, "image": image,
            "elapsed_seconds": time.monotonic() - started,
            "sha256": hashlib.sha256(data).hexdigest(), **metadata,
        })
        (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["runs"][0]["pixel_sha256"] == report["runs"][1]["pixel_sha256"]:
        raise RuntimeError("Different seeds produced identical pixels; investigate cached inference")
    (output_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: two CUDA 13 API generations verified. Evidence: {output_dir}")


if __name__ == "__main__":
    main()
