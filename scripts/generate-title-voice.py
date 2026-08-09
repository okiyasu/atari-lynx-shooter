#!/usr/bin/env python3
"""Generate and strictly verify VOICEVOX Nemo voice artifacts."""

import argparse
import datetime
import hashlib
import json
import platform
import struct
import tempfile
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENGINE_URL = "http://127.0.0.1:50121"
VOICEVOX_EDITOR_VERSION = "0.25.2"
NEMO_ENGINE_VERSION = "0.24.0"
NEMO_ENGINE_UUID = "208cf94d-43d2-4cf5-abc0-9783cac36d29"
NEMO_SPEAKER_LABEL = "男性2"
NEMO_ENGINE_SPEAKER_NAME = "男声2"
NEMO_SPEAKER_UUID = "7ecc7a17-1465-4b22-a3b5-842a110ff55e"
NEMO_STYLE_NAME = "ノーマル"
NEMO_STYLE_ID = 10000
NEMO_CV = "かちょゴリラ"
CREDIT = "VOICEVOX:Nemo（男性2）"
SAMPLE_RATE = 8000
TRAILING_SILENCE_SAMPLES = SAMPLE_RATE // 10
SYNTHESIS_SETTINGS = {
    "speedScale": 0.9,
    "pitchScale": -0.08,
    "intonationScale": 0.9,
    "volumeScale": 1.0,
    "prePhonemeLength": 0.1,
    "postPhonemeLength": 0.1,
    "outputSamplingRate": SAMPLE_RATE,
    "outputStereo": False,
}
INSTALLER = {
    "architecture": "arm64",
    "downloaded_at": "2026-08-09T10:31:21+09:00",
    "name": "voicevox_engine-macos-arm64-0.24.0.vvpp",
    "sha256": "d67cbe5c8e23c0ee41a398e12e20b98de039a0eada944a3938bc6c3e39fc8f4f",
    "url": (
        "https://github.com/VOICEVOX/voicevox_nemo_engine/releases/download/"
        "0.24.0/voicevox_engine-macos-arm64-0.24.0.vvpp"
    ),
}
EDITOR_INSTALLER = {
    "architecture": "arm64",
    "downloaded_at": "2026-08-09T10:28:51+09:00",
    "name": "VOICEVOX.0.25.2-arm64.dmg",
    "sha256": "4d532a84470c6d0cf713d2c5c6e6e5f8d2c36b18821055fd2c73386fcdfd6b91",
    "url": (
        "https://github.com/VOICEVOX/voicevox/releases/download/0.25.2/"
        "VOICEVOX.0.25.2-arm64.dmg"
    ),
}
LICENSE = {
    "checked_at": "2026-08-09",
    "credit": CREDIT,
    "nemo_terms_url": "https://voicevox.hiroshiba.jp/nemo/term/",
    "software_terms_url": "https://voicevox.hiroshiba.jp/term/",
    "summary": (
        "Nemo-generated audio is permitted for commercial and non-commercial "
        "use when credited; the fixed project credit is stricter than the "
        "minimum VOICEVOX Nemo credit."
    ),
    "restrictions": [
        "credit required",
        "no seriously offensive use",
        "no rights infringement or false authorship",
        "no criminal facilitation",
        "no machine-learning use",
        "no unauthorized software redistribution or reverse engineering",
    ],
}
HASH_POLICY = {
    "cross_run_reproducibility_required": [
        "query_sha256",
        "adpcm_sha256",
    ],
    "generation_run_provenance_only": [
        "wav_sha256",
        "pcm_sha256",
    ],
}
ASSETS = {
    "title": {
        "stem": "title-start",
        "macro": "TITLE_VOICE",
        "expected_text": "わしは宇宙の帝王ザカリテ",
        "expected_sample_count": 17408,
        "expected_query_sha256":
            "3092920fa47b189f5aa1b1577b859eb8bf7c07b080a067cfd4b05cff72f1fb7f",
        "expected_sha256":
            "99eb68abe7da548a7285510c86dec9417e94766d00ac30638de302a2cd6a1eb2",
    },
    "game-over": {
        "stem": "game-over",
        "macro": "GAME_OVER_VOICE",
        "expected_text": "お前は弱かった",
        "expected_sample_count": 11691,
        "expected_query_sha256":
            "b1f66cedab251ecec4cabe862f474c190061aa518147f7d74b92bd4d839c1d2f",
        "expected_sha256":
            "848691fea26de6e2503c67bed5721f1da27cab1692af81e2227a348ab412cb0f",
    },
}

INDEX_DELTA = (-1, -1, -1, -1, 2, 4, 6, 8)
STEP_TABLE = (
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371,
    408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166,
    1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749, 3024,
    3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845,
    8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500,
    20350, 22385, 24623, 27086, 29794, 32767,
)


def clamp(value, low, high):
    return max(low, min(high, value))


def is_sha256(value):
    return (
        isinstance(value, str) and
        len(value) == 64 and
        all(character in "0123456789abcdef" for character in value)
    )


def encode_sample(sample, predictor, step_index):
    difference = sample - predictor
    code = 0
    if difference < 0:
        code = 8
        difference = -difference
    step = STEP_TABLE[step_index]
    test_step = step
    if difference >= test_step:
        code |= 4
        difference -= test_step
    test_step >>= 1
    if difference >= test_step:
        code |= 2
        difference -= test_step
    test_step >>= 1
    if difference >= test_step:
        code |= 1

    delta = step >> 3
    if code & 1:
        delta += step >> 2
    if code & 2:
        delta += step >> 1
    if code & 4:
        delta += step
    predictor += -delta if code & 8 else delta
    predictor = clamp(predictor, -32768, 32767)
    step_index = clamp(step_index + INDEX_DELTA[code & 7], 0, 88)
    return code, predictor, step_index


def encode(samples):
    predictor = 0
    step_index = 0
    packed = bytearray()
    low = None
    for sample in samples:
        code, predictor, step_index = encode_sample(sample, predictor, step_index)
        if low is None:
            low = code
        else:
            packed.append(low | (code << 4))
            low = None
    if low is not None:
        packed.append(low)
    return bytes(packed)


def read_pcm(path):
    with wave.open(str(path), "rb") as source:
        wav_format = {
            "channels": source.getnchannels(),
            "compression": source.getcomptype(),
            "sample_rate_hz": source.getframerate(),
            "sample_width_bits": source.getsampwidth() * 8,
        }
        if wav_format != {
            "channels": 1,
            "compression": "NONE",
            "sample_rate_hz": SAMPLE_RATE,
            "sample_width_bits": 16,
        }:
            raise RuntimeError(f"unexpected VOICEVOX WAV format: {wav_format}")
        frames = source.readframes(source.getnframes())
        return struct.unpack("<{}h".format(len(frames) // 2), frames), wav_format


def asset_paths(asset):
    stem = asset["stem"]
    return {
        "text": ROOT / "assets" / "voice" / f"{stem}.txt",
        "adpcm": ROOT / "assets" / "voice" / f"{stem}.adpcm",
        "metadata": ROOT / "assets" / "voice" / f"{stem}.json",
        "header": ROOT / "include" / (
            "title_voice_data.h" if stem == "title-start"
            else "game_over_voice_data.h"
        ),
    }


def render_header(asset, sample_count, byte_count):
    macro = asset["macro"]
    guard = f"{macro}_DATA_H"
    return """#ifndef {guard}
#define {guard}

#define {macro}_SAMPLE_RATE 8000u
#define {macro}_SAMPLE_COUNT {sample_count}u
#define {macro}_ADPCM_BYTE_COUNT {byte_count}u
#define {macro}_INITIAL_PREDICTOR 0
#define {macro}_INITIAL_STEP_INDEX 0u

#endif
""".format(
        guard=guard, macro=macro, sample_count=sample_count, byte_count=byte_count
    )


def local_engine_url(engine_url, path, parameters=None):
    parsed = urllib.parse.urlsplit(engine_url)
    if parsed.scheme != "http" or parsed.hostname not in (
        "127.0.0.1", "localhost", "::1"
    ):
        raise RuntimeError("VOICEVOX generation is restricted to a local HTTP engine")
    base = engine_url.rstrip("/")
    query = urllib.parse.urlencode(parameters or {})
    return f"{base}{path}" + (f"?{query}" if query else "")


def request_json(engine_url, path, parameters=None, body=None):
    request = urllib.request.Request(
        local_engine_url(engine_url, path, parameters),
        data=body,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def verify_engine(engine_url):
    version = request_json(engine_url, "/version")
    if version != NEMO_ENGINE_VERSION:
        raise RuntimeError(
            f"VOICEVOX Nemo engine version {version!r}, expected {NEMO_ENGINE_VERSION!r}"
        )
    speakers = request_json(engine_url, "/speakers")
    matches = [
        speaker for speaker in speakers
        if speaker.get("speaker_uuid") == NEMO_SPEAKER_UUID
    ]
    if len(matches) != 1 or matches[0].get("name") != NEMO_ENGINE_SPEAKER_NAME:
        raise RuntimeError("official VOICEVOX Nemo male 2 speaker is unavailable")
    styles = matches[0].get("styles", [])
    if not any(
        style.get("id") == NEMO_STYLE_ID and
        style.get("name") == NEMO_STYLE_NAME and
        style.get("type") == "talk"
        for style in styles
    ):
        raise RuntimeError("official VOICEVOX Nemo male 2 style is unavailable")


def synthesize_wav(engine_url, text):
    verify_engine(engine_url)
    query = request_json(
        engine_url, "/audio_query", {"text": text, "speaker": NEMO_STYLE_ID}, b""
    )
    for key, value in SYNTHESIS_SETTINGS.items():
        query[key] = value
    query["kana"] = query.get("kana")
    query_body = json.dumps(
        query, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    request = urllib.request.Request(
        local_engine_url(engine_url, "/synthesis", {"speaker": NEMO_STYLE_ID}),
        data=query_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        wav = response.read()
    return wav, hashlib.sha256(query_body).hexdigest()


def engine_command():
    return (
        "/Users/mammycloud-m4/Library/Application Support/voicevox/"
        "vvpp-engines/208cf94d-43d2-4cf5-abc0-9783cac36d29/0.24.0/run "
        "--host 127.0.0.1 --port 50121 --disable_mutable_api"
    )


def generator_command(asset_name):
    return (
        "python3 scripts/generate-title-voice.py generate "
        f"--asset {asset_name} --engine-url {DEFAULT_ENGINE_URL}"
    )


def generate(asset_name, engine_url):
    asset = ASSETS[asset_name]
    paths = asset_paths(asset)
    text = paths["text"].read_text(encoding="utf-8").strip()
    if text != asset["expected_text"]:
        raise RuntimeError(f"{paths['text'].name} does not contain the approved exact phrase")
    wav, query_sha256 = synthesize_wav(engine_url, text)
    with tempfile.TemporaryDirectory(prefix=f"aps037-{asset['stem']}-voice-") as temp:
        wav_path = Path(temp) / f"{asset['stem']}.voicevox-nemo.wav"
        wav_path.write_bytes(wav)
        source_samples, wav_format = read_pcm(wav_path)
    if len(source_samples) < TRAILING_SILENCE_SAMPLES:
        raise RuntimeError("VOICEVOX WAV is shorter than the normalized silent tail")
    samples = tuple(source_samples[:-TRAILING_SILENCE_SAMPLES]) + (
        (0,) * TRAILING_SILENCE_SAMPLES
    )
    adpcm = encode(samples)
    digest = hashlib.sha256(adpcm).hexdigest()
    metadata = {
        "adpcm_bytes": len(adpcm),
        "adpcm_sha256": digest,
        "credit": CREDIT,
        "cv": NEMO_CV,
        "editor_installer": EDITOR_INSTALLER,
        "engine_command": engine_command(),
        "format": "IMA ADPCM 4-bit mono, low nibble first",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "generator_command": generator_command(asset_name),
        "hash_policy": HASH_POLICY,
        "initial_predictor": 0,
        "initial_step_index": 0,
        "input": text,
        "installer": INSTALLER,
        "license": LICENSE,
        "macos_architecture": platform.machine(),
        "pcm_postprocess": {
            "operation": "replace existing post-phoneme tail with exact zero",
            "trailing_silence_samples": TRAILING_SILENCE_SAMPLES,
        },
        "pcm_sha256": hashlib.sha256(
            struct.pack("<{}h".format(len(samples)), *samples)
        ).hexdigest(),
        "python": platform.python_version(),
        "query_sha256": query_sha256,
        "rosetta_used": False,
        "sample_count": len(samples),
        "sample_rate_hz": SAMPLE_RATE,
        "speaker": NEMO_SPEAKER_LABEL,
        "speaker_engine_name": NEMO_ENGINE_SPEAKER_NAME,
        "speaker_uuid": NEMO_SPEAKER_UUID,
        "style": NEMO_STYLE_NAME,
        "style_id": NEMO_STYLE_ID,
        "synthesis_settings": SYNTHESIS_SETTINGS,
        "voice_provider": "VOICEVOX Nemo",
        "voicevox_editor_version": VOICEVOX_EDITOR_VERSION,
        "voicevox_nemo_engine_uuid": NEMO_ENGINE_UUID,
        "voicevox_nemo_engine_version": NEMO_ENGINE_VERSION,
        "wav_format": wav_format,
        "wav_sha256": hashlib.sha256(wav).hexdigest(),
    }
    paths["adpcm"].write_bytes(adpcm)
    paths["metadata"].write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    paths["header"].write_text(
        render_header(asset, len(samples), len(adpcm)), encoding="ascii"
    )
    print(
        "generated {}: samples={} duration={:.6f}s adpcm_bytes={} sha256={}".format(
            asset_name, len(samples), len(samples) / SAMPLE_RATE, len(adpcm), digest
        )
    )


def verify_asset(asset_name):
    asset = ASSETS[asset_name]
    paths = asset_paths(asset)
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    adpcm = paths["adpcm"].read_bytes()
    text = paths["text"].read_text(encoding="utf-8").strip()
    digest = hashlib.sha256(adpcm).hexdigest()
    expected_header = render_header(asset, metadata["sample_count"], len(adpcm))
    checks = {
        "input": text == asset["expected_text"] == metadata.get("input"),
        "provider": metadata.get("voice_provider") == "VOICEVOX Nemo",
        "speaker": metadata.get("speaker") == NEMO_SPEAKER_LABEL and
            metadata.get("speaker_engine_name") == NEMO_ENGINE_SPEAKER_NAME and
            metadata.get("speaker_uuid") == NEMO_SPEAKER_UUID,
        "style": metadata.get("style") == NEMO_STYLE_NAME and
            metadata.get("style_id") == NEMO_STYLE_ID,
        "versions": metadata.get("voicevox_editor_version") ==
            VOICEVOX_EDITOR_VERSION and
            metadata.get("voicevox_nemo_engine_version") == NEMO_ENGINE_VERSION and
            metadata.get("voicevox_nemo_engine_uuid") == NEMO_ENGINE_UUID,
        "installer": metadata.get("installer") == INSTALLER and
            metadata.get("editor_installer") == EDITOR_INSTALLER,
        "license": metadata.get("license") == LICENSE and
            metadata.get("credit") == CREDIT,
        "settings": metadata.get("synthesis_settings") == SYNTHESIS_SETTINGS,
        "commands": metadata.get("engine_command") == engine_command() and
            metadata.get("generator_command") == generator_command(asset_name),
        "platform": metadata.get("macos_architecture") == "arm64" and
            metadata.get("rosetta_used") is False,
        "hash_policy": metadata.get("hash_policy") == HASH_POLICY,
        "pcm": metadata.get("pcm_postprocess") == {
            "operation": "replace existing post-phoneme tail with exact zero",
            "trailing_silence_samples": TRAILING_SILENCE_SAMPLES,
        } and is_sha256(metadata.get("pcm_sha256")),
        "wav": metadata.get("wav_format") == {
            "channels": 1,
            "compression": "NONE",
            "sample_rate_hz": SAMPLE_RATE,
            "sample_width_bits": 16,
        } and is_sha256(metadata.get("wav_sha256")) and
            metadata.get("query_sha256") == asset["expected_query_sha256"],
        "sample_rate": metadata.get("sample_rate_hz") == SAMPLE_RATE,
        "sample_count": metadata.get("sample_count") ==
            asset["expected_sample_count"],
        "byte_count": metadata.get("adpcm_bytes") == len(adpcm),
        "packed_length": len(adpcm) == (metadata.get("sample_count", 0) + 1) // 2,
        "sha256": metadata.get("adpcm_sha256") == digest,
        "pinned_sha256": asset["expected_sha256"] is not None and
            asset["expected_sha256"] == digest,
        "header": paths["header"].read_text(encoding="ascii") == expected_header,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(
            f"{asset_name} voice artifact verification failed: " + ", ".join(failed)
        )
    print(
        "{} VOICEVOX Nemo artifact verified: samples={} adpcm_bytes={} sha256={}".format(
            asset_name, metadata["sample_count"], len(adpcm), metadata["adpcm_sha256"]
        )
    )


def verify():
    verify_lossy_reproducibility_boundary()
    for asset_name in ASSETS:
        verify_asset(asset_name)


def verify_lossy_reproducibility_boundary():
    samples_a = (-40, -40, -40, -40)
    samples_b = (-39, -39, -39, -39)
    pcm_a = struct.pack("<4h", *samples_a)
    pcm_b = struct.pack("<4h", *samples_b)
    adpcm_a = encode(samples_a)
    adpcm_b = encode(samples_b)
    header_a = render_header(ASSETS["title"], len(samples_a), len(adpcm_a))
    header_b = render_header(ASSETS["title"], len(samples_b), len(adpcm_b))
    if (
        hashlib.sha256(pcm_a).digest() == hashlib.sha256(pcm_b).digest() or
        adpcm_a != adpcm_b or
        len(samples_a) != len(samples_b) or
        header_a != header_b
    ):
        raise RuntimeError("IMA ADPCM lossy reproducibility boundary regression")
    print(
        "IMA ADPCM boundary verified: different PCM provenance, "
        "identical ADPCM/sample count/header"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("--asset", choices=tuple(ASSETS), default="title")
    parser.add_argument("--engine-url", default=DEFAULT_ENGINE_URL)
    args = parser.parse_args()
    if args.command == "generate":
        generate(args.asset, args.engine_url)
    else:
        verify()


if __name__ == "__main__":
    main()
