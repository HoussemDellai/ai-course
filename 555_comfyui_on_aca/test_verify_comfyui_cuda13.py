import json
import struct
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from urllib import error

from verify_comfyui_cuda13 import ComfyUIClient, decode_png, prepare_workflow, require_cuda13


def png_chunk(kind, payload):
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))


def png():
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(b"\x00\x01\x02\x03"))
        + png_chunk(b"IEND", b"")
    )


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.client = ComfyUIClient("https://example.invalid")

    def test_requires_https(self):
        with self.assertRaises(ValueError):
            ComfyUIClient("http://example.invalid")

    def test_transport_retries_only_reads(self):
        failure = error.URLError("connection reset")
        with patch.object(self.client, "_get_bytes", side_effect=[failure, b"{}"]) as read, patch("time.sleep"):
            self.assertEqual(self.client.get_bytes("/history/p"), b"{}")
            self.assertEqual(read.call_count, 2)
        with patch.object(self.client, "_get_bytes", side_effect=failure) as post:
            with self.assertRaises(error.URLError):
                self.client.get_bytes("/prompt", body={"prompt": {}})
            self.assertEqual(post.call_count, 1)

    def test_runtime_evidence(self):
        stats = {"system": {"pytorch_version": "2.10.0+cu130"},
                 "devices": [{"type": "cuda", "name": "cuda:0 NVIDIA A100"}]}
        require_cuda13(stats)
        for version, device in (("2.10.0+cu126", "cuda"), ("2.10.0+cu130", "cpu")):
            with self.subTest(version=version, device=device):
                stats["system"]["pytorch_version"] = version
                stats["devices"][0]["type"] = device
                with self.assertRaises(RuntimeError):
                    require_cuda13(stats)

    def test_submission_validation(self):
        for response in ({}, {"prompt_id": "p", "node_errors": {"9": "bad"}},
                         {"prompt_id": "p", "error": "bad"}):
            with patch.object(self.client, "json", return_value=response):
                with self.assertRaises(RuntimeError):
                    self.client.submit({})

    def test_successful_history(self):
        image = {"filename": "test.png", "subfolder": "", "type": "output"}
        history = {"p": {"status": {"completed": True, "status_str": "success"},
                         "outputs": {"9": {"images": [image]}}}}
        with patch.object(self.client, "json", side_effect=[{}, history]), patch("time.sleep"):
            self.assertEqual(self.client.wait("p", "9", 5), image)

    def test_history_errors(self):
        for history in (
            {"status": {"status_str": "error", "completed": False}},
            {"status": {"messages": [["execution_interrupted", {}]]}},
            {"status": {"status_str": "success", "completed": True}, "outputs": {}},
            {"outputs": {}},
        ):
            with self.subTest(history=history), patch.object(self.client, "json", return_value={"p": history}):
                with self.assertRaises(RuntimeError):
                    self.client.wait("p", "9", 5)

    def test_timeout(self):
        with patch("time.monotonic", side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                self.client.wait("p", "9", 1)

    def test_readiness_timeout(self):
        with patch("time.monotonic", side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                self.client.ready(1)

    def test_http_and_malformed_json_fail(self):
        with patch.object(self.client, "get_bytes", return_value=b"[]"):
            with self.assertRaises(RuntimeError):
                self.client.json("/system_stats")
        with patch.object(self.client, "get_bytes", return_value=b"invalid"):
            with self.assertRaises(json.JSONDecodeError):
                self.client.json("/system_stats")
        failure = error.HTTPError("https://example.invalid", 400, "invalid", {}, None)
        with patch.object(self.client, "get_bytes", side_effect=failure):
            with self.assertRaises(error.HTTPError):
                self.client.json("/prompt")

    def test_workflow_overrides_and_models(self):
        original = json.loads(Path(__file__).with_name("image_z_image_turbo.json").read_text())
        objects = {}
        for node in original.values():
            required = {key: [[value]] for key, value in node["inputs"].items()
                        if key in ("unet_name", "clip_name", "vae_name", "sampler_name", "scheduler")}
            objects[node["class_type"]] = {"input": {"required": required}}
        workflow, save_node = prepare_workflow(original, objects, 42, "test")
        self.assertEqual(save_node, "9")
        self.assertEqual(workflow["57:3"]["inputs"]["seed"], 42)
        self.assertEqual(workflow["57:13"]["inputs"]["width"], 1024)
        self.assertNotEqual(original["57:3"]["inputs"]["seed"], 42)
        objects["UNETLoader"]["input"]["required"]["unet_name"] = [[]]
        with self.assertRaises(RuntimeError):
            prepare_workflow(original, objects, 42, "test")

    def test_png_decoding(self):
        self.assertEqual(decode_png(png(), (1, 1))["width"], 1)
        with self.assertRaises(ValueError):
            decode_png(png())
        for data in (b"HTML error", png()[:-1], png() + b"extra", png()[:40] + b"broken"):
            with self.subTest(data=data[:16]):
                with self.assertRaises(ValueError):
                    decode_png(data, (1, 1))


if __name__ == "__main__":
    unittest.main()
