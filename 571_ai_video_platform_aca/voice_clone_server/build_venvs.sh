#!/usr/bin/env bash
# One virtualenv per engine: their pinned dependencies (torch, transformers, numpy, ...) conflict.
# Everything is installed in a single RUN with hardlinks from a throw-away uv cache, so the identical torch
# files shared by the Qwen3-TTS, Chatterbox and OpenVoice environments are stored once in the image layer.
set -euxo pipefail

export UV_CACHE_DIR=/opt/uvcache UV_LINK_MODE=hardlink UV_PYTHON_INSTALL_DIR=/opt/uv-python
export NLTK_DATA=/opt/nltk_data
PY=/usr/local/bin/python3.11
COMMON="fastapi==0.141.1 uvicorn==0.54.0 python-multipart==0.0.32 soundfile"
mkdir -p /opt/venvs

# Qwen3-TTS (Apache-2.0)
uv venv /opt/venvs/qwen --python $PY
uv pip install --python /opt/venvs/qwen/bin/python torch==2.6.0 torchaudio==2.6.0 qwen-tts $COMMON
/opt/venvs/qwen/bin/python -c "from qwen_tts import Qwen3TTSModel"

# Chatterbox Multilingual (MIT)
uv venv /opt/venvs/chatterbox --python $PY
uv pip install --python /opt/venvs/chatterbox/bin/python torch==2.6.0 torchaudio==2.6.0 chatterbox-tts==0.1.7 "setuptools<81" $COMMON
/opt/venvs/chatterbox/bin/python -c "import perth; assert perth.PerthImplicitWatermarker is not None; from chatterbox.mtl_tts import ChatterboxMultilingualTTS"

# OpenVoice v2 (MIT): its repositories pin 2022-era dependencies, so install them without their metadata.
uv venv /opt/venvs/openvoice --python $PY
uv pip install --python /opt/venvs/openvoice/bin/python torch==2.6.0 torchaudio==2.6.0 \
    "numpy==1.23.5" "scipy<1.13" "setuptools<81" librosa==0.9.1 pydub==0.25.1 eng_to_ipa==0.0.2 inflect==7.0.0 unidecode==1.3.7 \
    pypinyin==0.50.0 cn2an==0.5.22 jieba==0.42.1 langid==1.1.6 huggingface_hub \
    txtsplit cached_path transformers==4.44.2 num2words==0.5.12 unidic_lite==1.0.8 mecab-python3==1.0.9 \
    pykakasi==2.2.1 fugashi==1.3.0 g2p_en==2.1.0 anyascii==0.3.2 jamo==0.4.1 "gruut[de,es,fr]==2.2.3" g2pkk \
    loguru==0.7.2 tqdm nltk $COMMON
uv pip install --python /opt/venvs/openvoice/bin/python --no-deps \
    "git+https://github.com/myshell-ai/OpenVoice.git" "git+https://github.com/myshell-ai/MeloTTS.git"
/opt/venvs/openvoice/bin/python -m nltk.downloader -d "$NLTK_DATA" \
    averaged_perceptron_tagger averaged_perceptron_tagger_eng cmudict punkt punkt_tab
/opt/venvs/openvoice/bin/python -c "from openvoice.api import OpenVoiceBaseClass, ToneColorConverter; from melo.api import TTS"

# Fish Audio S2 Pro (research license, non-commercial): official source, run through its API server.
git clone https://github.com/fishaudio/fish-speech /opt/fish-speech
git -C /opt/fish-speech checkout "$FISH_SPEECH_COMMIT"
cd /opt/fish-speech
UV_PROJECT_ENVIRONMENT=/opt/venvs/fish uv sync --python 3.12 --extra cu126
/opt/venvs/fish/bin/python -c "import fish_speech"

rm -rf /opt/uvcache /root/.cache
