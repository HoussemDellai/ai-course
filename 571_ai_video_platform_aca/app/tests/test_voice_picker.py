import asyncio
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from video_platform.api import create_app
from video_platform.config import Settings
from video_platform.speech import SpeechError, VoiceCapabilities, VoiceCatalog, fetch_voices
from video_platform.storage import LocalArtifactStore

CREDENTIAL = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="test-only"))

VOICE_LIST = [
    {"Name": "Microsoft Server Speech Text to Speech Voice (fr-FR, DeniseNeural)", "DisplayName": "Denise",
     "LocalName": "Denise", "ShortName": "fr-FR-DeniseNeural", "Gender": "Female", "Locale": "fr-FR",
     "LocaleName": "French (France)", "StyleList": ["cheerful", "sad"], "SampleRateHertz": "48000",
     "VoiceType": "Neural", "Status": "GA", "WordsPerMinute": "150"},
    {"DisplayName": "Jenny", "LocalName": "Jenny", "ShortName": "en-US-JennyNeural", "Gender": "Female",
     "Locale": "en-US", "LocaleName": "English (United States)", "StyleList": ["chat", "cheerful"],
     "VoiceType": "Neural", "Status": "GA"},
    {"DisplayName": "Ava Multilingual", "ShortName": "en-US-AvaMultilingualNeural", "Gender": "Female",
     "Locale": "en-US", "SecondaryLocaleList": ["fr-FR", "es-ES"], "VoiceType": "Neural", "Status": "GA"},
    {"DisplayName": "Ava HD", "ShortName": "en-US-Ava:DragonHDLatestNeural", "Gender": "Female",
     "Locale": "en-US", "VoiceType": "Neural", "Status": "Preview"},
    {"ShortName": "en-GB-MinimalNeural", "Locale": "en-GB", "VoiceType": "Neural"},
]


def response(url, payload=None, status_code=200):
    return httpx.Response(status_code, request=httpx.Request("GET", url), json=VOICE_LIST if payload is None else payload)


def test_voice_summary_exposes_what_the_picker_needs():
    voices = {v["ShortName"]: VoiceCapabilities.model_validate(v) for v in VOICE_LIST}
    denise = voices["fr-FR-DeniseNeural"].summary()
    assert denise == {
        "name": "fr-FR-DeniseNeural", "display_name": "Denise", "local_name": "Denise", "gender": "Female",
        "locale": "fr-FR", "locale_name": "French (France)", "secondary_locales": [],
        "styles": ["cheerful", "sad"], "type": "Neural", "status": "GA", "delivery_controls": True,
    }
    assert voices["en-US-AvaMultilingualNeural"].summary()["secondary_locales"] == ["fr-FR", "es-ES"]
    assert voices["en-US-Ava:DragonHDLatestNeural"].summary()["delivery_controls"] is False
    minimal = voices["en-GB-MinimalNeural"].summary()
    assert minimal["display_name"] == "en-GB-MinimalNeural" and minimal["gender"] == "" and minimal["styles"] == []


def test_fetch_voices_calls_the_speech_endpoint_with_entra_token(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return response(url)

    monkeypatch.setattr("video_platform.speech.httpx.get", get)
    voices = fetch_voices("https://speech.example.com/", CREDENTIAL)
    assert [v.name for v in voices][:2] == ["fr-FR-DeniseNeural", "en-US-JennyNeural"] and len(voices) == 5
    url, kwargs = calls[0]
    assert url == "https://speech.example.com/tts/cognitiveservices/voices/list"
    assert kwargs["headers"] == {"Authorization": "Bearer test-only"}

    monkeypatch.setattr("video_platform.speech.httpx.get", lambda url, **kw: response(url, status_code=503))
    with pytest.raises(SpeechError, match="Could not load voice capabilities"):
        fetch_voices("https://speech.example.com", CREDENTIAL)


async def test_voice_catalog_caches_and_refreshes(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return response(url)

    monkeypatch.setattr("video_platform.speech.httpx.get", get)
    catalog = VoiceCatalog("https://speech.example.com", CREDENTIAL)
    results = await asyncio.gather(catalog.voices(), catalog.voices(), catalog.voices())
    assert len(calls) == 1 and all(len(r) == 5 for r in results)
    await catalog.voices()
    assert len(calls) == 1

    expiring = VoiceCatalog("https://speech.example.com", CREDENTIAL, ttl_seconds=0)
    await expiring.voices()
    await expiring.voices()
    assert len(calls) == 3


class FakeCatalog:
    def __init__(self, error=None):
        self.error = error

    async def voices(self):
        if self.error:
            raise self.error
        return [VoiceCapabilities.model_validate(v) for v in VOICE_LIST]


def make_client(tmp_path, catalog, api_key="test-key"):
    settings = Settings(work_dir=tmp_path / "work", local_output_dir=tmp_path / "out", api_key=api_key,
                        tts_voice="en-US-JennyNeural")
    store = LocalArtifactStore(settings.local_output_dir)

    async def close():
        pass

    return TestClient(create_app(settings, services=(store, lambda manager: None, close), voice_catalog=catalog))


def test_voices_endpoint_lists_every_voice_sorted_and_requires_the_api_key(tmp_path):
    with make_client(tmp_path, FakeCatalog()) as client:
        assert client.get("/api/voices").status_code == 401
        body = client.get("/api/voices", headers={"X-API-Key": "test-key"}).json()
    assert body["configured"] is True and body["default_voice"] == "en-US-JennyNeural"
    assert [v["name"] for v in body["voices"]] == [
        "en-GB-MinimalNeural", "en-US-Ava:DragonHDLatestNeural", "en-US-AvaMultilingualNeural",
        "en-US-JennyNeural", "fr-FR-DeniseNeural",
    ]
    assert body["voices"][3]["styles"] == ["chat", "cheerful"]
    assert body["voices"][1]["delivery_controls"] is False


def test_voices_endpoint_reports_unconfigured_speech_and_upstream_failures(tmp_path):
    with make_client(tmp_path, None) as client:
        assert client.get("/api/voices", headers={"X-API-Key": "test-key"}).json() == {
            "configured": False, "default_voice": "en-US-JennyNeural", "voices": [],
        }
    failing = FakeCatalog(SpeechError("Could not load voice capabilities from the Speech endpoint: boom"))
    with make_client(tmp_path, failing) as client:
        reply = client.get("/api/voices", headers={"X-API-Key": "test-key"})
    assert reply.status_code == 502 and "boom" in reply.json()["detail"]


PICKER_SCRIPT = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const voices = JSON.parse(process.argv[2]);
const failVoices = process.argv[3] === "fail";
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  const attributes = html.slice(html.lastIndexOf("<", match.index), html.indexOf(">", match.index));
  elements.set(match[1], {
    value: attributes.match(/\bvalue="([^"]*)"/)?.[1] || "",
    checked: /\bchecked\b/.test(attributes), disabled: /\bdisabled\b/.test(attributes),
    hidden: /\bhidden\b/.test(attributes), innerHTML: "", textContent: "",
    style: {}, classList: {add() {}, remove() {}, toggle() {}},
    addEventListener() {}, focus() {}, querySelectorAll() {return []}
  });
}
const el = id => {
  assert(elements.has(id), `Missing DOM element ${id}`);
  return elements.get(id);
};
const posts = [], voiceRequests = [];
const context = {
  document: {getElementById: el, addEventListener() {}, querySelectorAll() {return []}, hidden: true},
  window: {addEventListener() {}}, localStorage: {getItem() {return ""}},
  location: {hash: ""}, setInterval() {}, clearInterval() {}, setTimeout() {}, clearTimeout() {},
  alert(message) {throw new Error(message)}, console, URL, FormData, Intl,
  async fetch(url, options = {}) {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
      return {ok: true, status: 202, async json() {return {id: "created", request: posts.at(-1)}}};
    }
    if (String(url).startsWith("/api/voices")) {
      voiceRequests.push(url);
      if (failVoices) return {ok: false, status: 502, async json() {return {detail: "boom"}}};
      return {ok: true, async json() {return {configured: true, default_voice: "en-US-JennyNeural", voices}}};
    }
    return {ok: true, async json() {return []}};
  },
};
vm.createContext(context);
vm.runInContext(script, context);
const settle = async () => { for (let i = 0; i < 5; i++) await new Promise(resolve => setImmediate(resolve)); };
const values = id => [...el(id).innerHTML.matchAll(/<option value="([^"]*)"/g)].map(m => m[1]);
const submit = async () => { await el("form").onsubmit({preventDefault() {}}); };
const delivery = () => { el("naturalistic").checked = true; el("naturalistic").onchange(); };

(async () => {
  await settle();
  assert.equal(voiceRequests.length, 1);
  if (failVoices) {
    assert.equal(el("voicePicker").hidden, true);
    assert.equal(el("voice").hidden, false);
    assert.equal(el("speechStyle").hidden, false);
    assert.equal(el("speechStylePicker").hidden, true);
    el("prompt").value = "A lighthouse"; el("voice").value = "custom-voice"; delivery();
    el("speechStyle").value = "calm";
    await submit();
    assert.equal(posts[0].voice, "custom-voice");
    assert.equal(posts[0].delivery.style, "calm");
    return;
  }
  // All voices are listed, grouped by language, with a language filter and a default entry.
  assert.equal(el("voicePicker").hidden, false);
  assert.equal(el("voice").hidden, true);
  assert.equal(el("voiceLabel").hidden, true);
  assert.deepEqual(values("voiceSelect"), [
    "", "en-GB-MinimalNeural", "en-US-Ava:DragonHDLatestNeural", "en-US-AvaMultilingualNeural",
    "en-US-JennyNeural", "fr-FR-DeniseNeural",
  ]);
  assert.match(el("voiceSelect").innerHTML, /<optgroup label="[^"]*English \(United States\) · en-US">/);
  assert.match(el("voiceSelect").innerHTML, /<optgroup label="[^"]*French \(France\) · fr-FR">/);
  assert.match(el("voiceSelect").innerHTML, /Default \(Jenny \(Female\)\)/);
  assert.match(el("voiceSelect").innerHTML, /Ava HD \(Female\) \[Preview\] - no rate\/style/);
  assert.match(el("voiceLocale").innerHTML, /All languages \(5 voices\)/);
  assert.deepEqual(values("voiceLocale"), ["", "en-GB", "en-US", "fr-FR", "es-ES"]);
  assert.match(el("voiceLocale").innerHTML, /French \(France\) · fr-FR \(2\)/);

  // Filtering by language also offers multilingual voices; choosing one fills the real voice field.
  el("voiceLocale").value = "fr-FR"; el("voiceLocale").onchange();
  assert.deepEqual(values("voiceSelect"), ["", "fr-FR-DeniseNeural", "en-US-AvaMultilingualNeural"]);
  el("voiceSelect").value = "fr-FR-DeniseNeural"; el("voiceSelect").onchange();
  assert.equal(el("voice").value, "fr-FR-DeniseNeural");
  assert.match(el("voiceInfo").textContent, /fr-FR-DeniseNeural · Female · French \(France\) \(fr-FR\) · 2 speaking styles/);
  el("voiceLocale").value = "en-US"; el("voiceLocale").onchange();
  assert.match(el("voiceSelect").innerHTML, /<option value="fr-FR-DeniseNeural" selected>[^<]*\(current selection\)/);

  // Styles come from the chosen voice, and a style the new voice lacks is cleared.
  assert.deepEqual(values("speechStylePicker"), ["", "cheerful", "sad"]);
  assert.equal(el("speechStyle").hidden, true);
  assert.equal(el("speechStylePicker").hidden, false);
  el("speechStylePicker").value = "sad"; el("speechStylePicker").onchange();
  assert.equal(el("speechStyle").value, "sad");
  el("voiceSelect").value = "en-US-JennyNeural"; el("voiceSelect").onchange();
  assert.deepEqual(values("speechStylePicker"), ["", "chat", "cheerful"]);
  assert.equal(el("speechStyle").value, "");
  el("speechStylePicker").value = "cheerful"; el("speechStylePicker").onchange();
  el("voiceSelect").value = ""; el("voiceSelect").onchange();
  assert.equal(el("voice").value, "");
  assert.equal(el("speechStyle").value, "cheerful", "the default voice (Jenny) also supports cheerful");
  el("voiceSelect").value = "en-US-AvaMultilingualNeural"; el("voiceSelect").onchange();
  assert.deepEqual(values("speechStylePicker"), [""]);
  assert.match(el("styleInfo").textContent, /no speaking styles/);
  assert.match(el("voiceInfo").textContent, /multilingual: also 2 other languages/);
  el("voiceSelect").value = "en-US-Ava:DragonHDLatestNeural"; el("voiceSelect").onchange();
  assert.match(el("voiceInfo").textContent, /HD and preview voices cannot use rate or style/);

  // The selection is what gets submitted.
  el("voiceSelect").value = "fr-FR-DeniseNeural"; el("voiceSelect").onchange();
  el("speechStylePicker").value = "cheerful"; el("speechStylePicker").onchange();
  el("prompt").value = "A lighthouse"; delivery();
  await submit();
  assert.equal(posts[0].voice, "fr-FR-DeniseNeural");
  assert.equal(posts[0].delivery.style, "cheerful");

  // Narration off or cloned voices disable the pickers just like the text field.
  el("narration").checked = false; el("narration").onchange();
  assert.equal(el("voiceSelect").disabled, true);
  assert.equal(el("voiceLocale").disabled, true);
  el("narration").checked = true; el("narration").onchange();
  assert.equal(el("voiceSelect").disabled, false);

  // Batch variants pick voices from the same catalog; style choices are those every variant shares.
  el("batchEnabled").checked = true; el("batchEnabled").onchange();
  assert.equal(el("voiceSelect").disabled, true);
  assert.match(el("variants").innerHTML, /<select class="input" aria-label="Variant 1 Azure voice" data-index="0" data-field="voice"/);
  assert.match(el("variants").innerHTML, /fr-FR-DeniseNeural/);
  const variantsHtml = el("variants").innerHTML;
  el("variants").onchange({target: {dataset: {index: "0", field: "voice"}, value: "fr-FR-DeniseNeural"}});
  el("variants").onchange({target: {dataset: {index: "1", field: "voice"}, value: "en-US-JennyNeural"}});
  assert.deepEqual(values("speechStylePicker"), ["", "cheerful"]);
  assert.match(el("styleInfo").textContent, /shared by every variant voice/);
  el("variants").onchange({target: {dataset: {index: "1", field: "voice"}, value: "en-US-AvaMultilingualNeural"}});
  assert.deepEqual(values("speechStylePicker"), [""]);
  assert.match(el("styleInfo").textContent, /share no speaking style/);
  assert.equal(el("variants").innerHTML, variantsHtml, "Choosing a voice must not re-render the rows");
  el("variants").onchange({target: {dataset: {index: "1", field: "voice"}, value: "typed-by-hand"}});
  assert.equal(el("speechStyle").hidden, false, "an unknown voice falls back to free-text style entry");
  assert.equal(el("speechStylePicker").hidden, true);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
@pytest.mark.parametrize("mode", ["catalog", "fail"])
def test_browser_voice_and_style_pickers(mode):
    import json

    html = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    summaries = [VoiceCapabilities.model_validate(v).summary() for v in VOICE_LIST]
    summaries.sort(key=lambda v: (v["locale"].lower(), v["display_name"].lower(), v["name"]))
    result = subprocess.run(["node", "-e", PICKER_SCRIPT, str(html), json.dumps(summaries), mode],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
