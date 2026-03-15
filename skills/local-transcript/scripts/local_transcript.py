#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "mlx-whisper>=0.4.0",
#   "mlx-lm>=0.22.0",
#   "faster-whisper>=1.2.1",
#   "opencc-python-reimplemented>=0.1.7",
#   "python-docx>=1.1.2",
#   "reportlab>=4.0.0",
# ]
# ///

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from opencc import OpenCC
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


PDF_CJK_FONT_CANDIDATES = [
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
]
PDF_CJK_FONT_NAME = "LocalTranscriptCJK"
MODEL_DOWNLOAD_ROOT = Path("/tmp/local-transcript/models")
CACHE_ROOT = Path("/tmp/local-transcript/cache")
AUDIO_CACHE_VERSION = "2026-03-14-v3"
RAW_TRANSCRIPT_CACHE_VERSION = "2026-03-14-v3"
CLEAN_TRANSCRIPT_CACHE_VERSION = "2026-03-14-v11"
MLX_LLM_DEFAULT_MODEL = "mlx-community/Qwen2.5-7B-Instruct-4bit"
MLX_LLM_FAST_MODEL = "mlx-community/Qwen2.5-3B-Instruct-4bit"
CHINESE_CHAR_RE = re.compile(r"[\u3400-\u9fff]")
TIMESTAMP_RE = re.compile(r"^\s*\[[0-9:\.\-\>\s]+\]\s*")
DEFAULT_KEEP_TEMP_ARTIFACTS = ("wav", "raw.json")

MLX_MODEL_MAP = {
    "fast": "mlx-community/whisper-small",
    "balanced": "mlx-community/whisper-large-v3-turbo",
    "accurate": "mlx-community/whisper-large-v3-turbo",
}

FASTER_WHISPER_MODE_PRESETS: dict[str, dict[str, object]] = {
    "fast": {
        "model_ref": "base",
        "compute_type": "int8",
        "beam_size": 1,
        "best_of": 1,
        "condition_on_previous_text": False,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 400, "speech_pad_ms": 200},
        "chunk_length": 18,
        "workers_cap": 8,
        "no_speech_threshold": 0.55,
    },
    "balanced": {
        "model_ref": "small",
        "compute_type": "int8",
        "beam_size": 4,
        "best_of": 3,
        "condition_on_previous_text": False,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 500, "speech_pad_ms": 250},
        "chunk_length": 28,
        "workers_cap": 6,
        "no_speech_threshold": 0.6,
    },
    "accurate": {
        "model_ref": "medium",
        "compute_type": "int8",
        "beam_size": 6,
        "best_of": 5,
        "condition_on_previous_text": False,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 650, "speech_pad_ms": 320},
        "chunk_length": 36,
        "workers_cap": 4,
        "no_speech_threshold": 0.65,
    },
}

ZH_REPLACEMENTS = {
    # ASR systematic errors: token spacing / casing
    "V P N": "VPN",
    "VPM": "VPN",
    "TCPdrop": "TCP Drop",
    "Shadow socks": "Shadowsocks",
    # High-frequency Chinese homophones that Whisper consistently gets wrong
    "大便车": "搭便车",
    "配剂制": "配给制",
    "静若寒蝉": "噤若寒蝉",
    "肥皂炮": "肥皂泡",
    "寄入活产": "计入活产",
    "瞄懂": "秒懂",
    "虚视": "叙事",
    "复旧感": "负疚感",
    "矮变": "癌变",
    "百度人": "摆渡人",
    "步道词": "布道词",
    "古灵测试": "骨龄测试",
    "进入区": "禁入区",
    "灿案": "惨案",
    "奇外死亡": "奇怪死亡",
}

EN_REPLACEMENTS = {
    "V P N": "VPN",
    "Shadow socks": "Shadowsocks",
    "TCPdrop": "TCP Drop",
}

LLM_PROOFREAD_PROMPT = """\
你是中文语音转文字(ASR)校对专家。以下文本来自Whisper语音识别，包含大量同音/近音错字。

请逐句检查并修正所有错误。对每个可疑的字词，问自己："在这个语境下，这个词说得通吗？有没有一个同音/近音的词更合理？"

常见ASR错误模式（举例，不限于此）：
- 同音字：取体→躯体、谦戏→迁徙、河流→合流（致命力量的"合流"）、把子→靶子、进取→进去、冰死→濒死、新死→心死
- 近音字：精掉→惊掉、莫尼黑→慕尼黑、自理行间→字里行间、原分不动→原封不动、金明盟→基民盟
- 成语/固定搭配错字：引颈受禄→引颈就戮、三观近悔→三观尽毁、人口置患→人口置换
- 专有名词：地名(慕尼黑/兰佩杜萨)、人名、书名、政治术语、哲学概念(忒修斯之船)必须用标准写法
- 繁简混用：统一简体

规则：
1. 修正所有你能识别的错误，宁可多修正也不要漏掉
2. 不改变原文意思、语气和结构，不删除或添加内容
3. 保持原文的换行位置不变，不要合并或拆分段落
4. 直接输出校对后的全部文本，不输出任何解释、标注或说明
5. 不要在输出前加任何前缀（如"校对后文本："等）"""


@dataclass(frozen=True)
class ModeConfig:
    name: str
    backend: str
    model_ref: str
    compute_type: str
    beam_size: int
    best_of: int
    condition_on_previous_text: bool
    vad_filter: bool
    vad_parameters: dict[str, float | int]
    chunk_length: int
    num_workers: int
    cpu_threads: int
    no_speech_threshold: float


@dataclass(frozen=True)
class RawTranscript:
    language: str
    raw_text: str
    segments: list[dict[str, float | str]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe a local media file into cleaned txt, pdf, or docx outputs."
    )
    parser.add_argument("input", help="Absolute or relative path to a local media file")
    parser.add_argument("--output", help="Explicit output path for a single requested format")
    parser.add_argument("--output-dir", help="Directory to place the final transcript file(s) in")
    parser.add_argument(
        "--format",
        dest="formats",
        action="append",
        choices=("txt", "pdf", "docx"),
        help="Output format. Repeat to write multiple formats. Defaults to txt.",
    )
    parser.add_argument(
        "--mode",
        choices=("fast", "balanced", "accurate"),
        default="balanced",
        help="Speed/quality preset for ASR. Defaults to balanced.",
    )
    parser.add_argument(
        "--backend",
        choices=("mlx", "faster-whisper"),
        default="mlx",
        help="ASR backend. mlx uses Apple Silicon GPU (default). faster-whisper uses CPU.",
    )
    parser.add_argument(
        "--model-path",
        help="Optional model override. For mlx: a HuggingFace repo. For faster-whisper: a model name or path.",
    )
    parser.add_argument(
        "--llm-backend",
        choices=("local", "claude", "none"),
        default="local",
        help="LLM backend for proofreading. 'local' uses mlx-lm + Qwen2.5 on Apple Silicon (default). "
             "'claude' uses claude CLI. 'none' skips LLM proofreading.",
    )
    parser.add_argument(
        "--llm-model",
        help="Override the local LLM model (HuggingFace repo for mlx-lm). "
             f"Default: {MLX_LLM_DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--no-llm-proofread",
        action="store_true",
        help="Shorthand for --llm-backend none.",
    )
    parser.add_argument(
        "--llm-proofread-en",
        action="store_true",
        help="Enable LLM proofreading for English transcripts (off by default).",
    )
    parser.add_argument(
        "--language",
        help="Language hint for ASR (e.g. 'zh', 'en'). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--force-transcribe",
        action="store_true",
        help="Ignore raw/clean transcript caches and rerun ASR.",
    )
    parser.add_argument(
        "--replacements-file",
        help="Path to a JSON file with additional {wrong: correct} replacements to apply.",
    )
    parser.add_argument("--keep-temp", action="store_true", help="Keep intermediate files for debugging")
    return parser.parse_args()


def fail(message: str, exit_code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def require_command(name: str) -> str:
    path = shutil.which(name)
    if not path:
        fail(f"Required dependency not available: {name}")
    return path


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, check=True, text=True, capture_output=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        summary = detail.splitlines()[-1] if detail else "subprocess failed without stderr"
        fail(f"Command failed: {' '.join(cmd)} | {summary}")


def normalize_formats(formats: list[str] | None) -> list[str]:
    if not formats:
        return ["txt"]
    deduped: list[str] = []
    for fmt in formats:
        if fmt not in deduped:
            deduped.append(fmt)
    return deduped


def default_output_path(base_dir: Path, input_path: Path, fmt: str) -> Path:
    return base_dir / f"{input_path.stem}-transcript.{fmt}"


def resolve_mode_config(mode: str, backend: str, model_path: str | None = None) -> ModeConfig:
    cpu_threads = max(1, os.cpu_count() or 4)

    if backend == "mlx":
        model_ref = model_path or MLX_MODEL_MAP.get(mode, "mlx-community/whisper-large-v3-turbo")
        return ModeConfig(
            name=mode,
            backend="mlx",
            model_ref=model_ref,
            compute_type="float16",
            beam_size=5 if mode == "accurate" else 1,
            best_of=1,
            condition_on_previous_text=False,
            vad_filter=False,
            vad_parameters={},
            chunk_length=30,
            num_workers=1,
            cpu_threads=cpu_threads,
            no_speech_threshold=0.6,
        )

    if mode not in FASTER_WHISPER_MODE_PRESETS:
        fail(f"Unsupported mode: {mode}")
    preset = FASTER_WHISPER_MODE_PRESETS[mode]
    workers_cap = int(preset["workers_cap"])
    resolved_model = model_path or str(preset["model_ref"])
    return ModeConfig(
        name=mode,
        backend="faster-whisper",
        model_ref=resolved_model,
        compute_type=str(preset["compute_type"]),
        beam_size=int(preset["beam_size"]),
        best_of=int(preset["best_of"]),
        condition_on_previous_text=bool(preset["condition_on_previous_text"]),
        vad_filter=bool(preset["vad_filter"]),
        vad_parameters=dict(preset["vad_parameters"]),
        chunk_length=int(preset["chunk_length"]),
        num_workers=max(1, min(cpu_threads, workers_cap)),
        cpu_threads=cpu_threads,
        no_speech_threshold=float(preset["no_speech_threshold"]),
    )


def build_mode_identity(mode_config: ModeConfig) -> str:
    return json.dumps(asdict(mode_config), ensure_ascii=False, sort_keys=True)


def resolve_media_fingerprint(input_path: Path) -> str:
    stat = input_path.stat()
    return hashlib.sha256(
        f"{input_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}".encode("utf-8")
    ).hexdigest()


def resolve_audio_cache_path(input_path: Path) -> Path:
    media_key = resolve_media_fingerprint(input_path)
    cache_key = hashlib.sha256(f"{AUDIO_CACHE_VERSION}|{media_key}".encode("utf-8")).hexdigest()
    return CACHE_ROOT / "audio" / f"{cache_key}.wav"


def resolve_raw_cache_path(input_path: Path, mode_config: ModeConfig) -> Path:
    media_key = resolve_media_fingerprint(input_path)
    cache_key = hashlib.sha256(
        f"{RAW_TRANSCRIPT_CACHE_VERSION}|{media_key}|{build_mode_identity(mode_config)}".encode("utf-8")
    ).hexdigest()
    return CACHE_ROOT / "raw" / f"{cache_key}.json"


def resolve_clean_cache_path(input_path: Path, raw_text: str, language_hint: str | None, llm_enabled: bool) -> Path:
    media_key = resolve_media_fingerprint(input_path)
    raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    language_key = (language_hint or "auto").strip().lower()
    llm_key = "llm" if llm_enabled else "nollm"
    cache_key = hashlib.sha256(
        f"{CLEAN_TRANSCRIPT_CACHE_VERSION}|{media_key}|{raw_hash}|{language_key}|{llm_key}".encode("utf-8")
    ).hexdigest()
    return CACHE_ROOT / "clean" / f"{cache_key}.json"


def load_raw_transcript_cache(cache_path: Path) -> RawTranscript | None:
    if not cache_path.exists():
        return None
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    language = data.get("language")
    raw_text = data.get("raw_text")
    segments = data.get("segments")
    if not language or not raw_text or not isinstance(segments, list):
        return None
    return RawTranscript(language=language, raw_text=raw_text, segments=segments)


def save_raw_transcript_cache(cache_path: Path, transcript: RawTranscript) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(asdict(transcript), ensure_ascii=False),
        encoding="utf-8",
    )


def load_clean_transcript_cache(cache_path: Path) -> tuple[str, str] | None:
    if not cache_path.exists():
        return None
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    language = data.get("language")
    final_text = data.get("final_text")
    if not language or not final_text:
        return None
    return language, final_text


def save_clean_transcript_cache(cache_path: Path, language: str, final_text: str) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"language": language, "final_text": final_text}, ensure_ascii=False),
        encoding="utf-8",
    )


def resolve_output_paths(
    input_path: Path, output: str | None, output_dir: str | None, formats: list[str],
) -> dict[str, Path]:
    if output and output_dir:
        fail("Use either --output or --output-dir, not both")
    if output:
        if len(formats) != 1:
            fail("Explicit --output supports only a single output format")
        return {formats[0]: Path(output).expanduser().resolve()}
    base_dir = Path(output_dir).expanduser().resolve() if output_dir else input_path.parent
    return {fmt: default_output_path(base_dir, input_path, fmt) for fmt in formats}


def ensure_audio_cache(ffmpeg: str, input_path: Path, audio_cache_path: Path) -> tuple[Path, str]:
    if audio_cache_path.exists() and audio_cache_path.stat().st_size > 0:
        return audio_cache_path, "hit"
    audio_cache_path.parent.mkdir(parents=True, exist_ok=True)
    run_cmd([
        ffmpeg, "-y", "-i", str(input_path),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(audio_cache_path),
    ])
    return audio_cache_path, "miss"


# ---------------------------------------------------------------------------
# ASR Backend: mlx-whisper (Apple Silicon GPU/ANE)
# ---------------------------------------------------------------------------

def transcribe_audio_mlx(mode_config: ModeConfig, wav_path: Path, language_hint: str | None = None) -> RawTranscript:
    try:
        import mlx_whisper
    except ImportError:
        fail("Required dependency not available: mlx-whisper. Install with: pip install mlx-whisper")

    try:
        import mlx.core as mx
        mx.metal.set_cache_limit(512 * 1024 * 1024)
    except Exception:
        pass

    print(f"  mlx-whisper: loading model {mode_config.model_ref} ...")
    t0 = time.time()

    try:
        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=mode_config.model_ref,
            language=language_hint,
            word_timestamps=False,
            fp16=True,
            condition_on_previous_text=False,
        )
    except Exception as exc:
        fail(f"mlx-whisper transcription failed: {exc}")

    elapsed = time.time() - t0
    print(f"  mlx-whisper: transcription completed in {elapsed:.1f}s")

    segments: list[dict[str, float | str]] = []
    text_chunks: list[str] = []
    for seg in result.get("segments", []):
        text = seg.get("text", "").strip()
        if not text:
            continue
        segments.append({
            "start": float(seg.get("start", 0)),
            "end": float(seg.get("end", 0)),
            "text": text,
        })
        text_chunks.append(text)

    raw_text = "\n".join(text_chunks).strip()
    if not raw_text:
        fail("Transcription produced an empty transcript")

    language_hint = result.get("language", "") or ""
    if not language_hint:
        language_hint = infer_language(normalize_lines(raw_text))

    return RawTranscript(language=language_hint, raw_text=raw_text, segments=segments)


# ---------------------------------------------------------------------------
# ASR Backend: faster-whisper (CPU fallback)
# ---------------------------------------------------------------------------

def transcribe_audio_faster_whisper(mode_config: ModeConfig, wav_path: Path, language_hint: str | None = None) -> RawTranscript:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        fail("Required dependency not available: faster-whisper")

    MODEL_DOWNLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    print(f"  faster-whisper: loading model {mode_config.model_ref} ...")
    t0 = time.time()

    try:
        model = WhisperModel(
            mode_config.model_ref,
            device="auto",
            compute_type=mode_config.compute_type,
            cpu_threads=mode_config.cpu_threads,
            num_workers=mode_config.num_workers,
            download_root=str(MODEL_DOWNLOAD_ROOT),
        )
    except ValueError:
        if mode_config.compute_type == "default":
            raise
        model = WhisperModel(
            mode_config.model_ref,
            device="auto",
            compute_type="default",
            cpu_threads=mode_config.cpu_threads,
            num_workers=mode_config.num_workers,
            download_root=str(MODEL_DOWNLOAD_ROOT),
        )
    except Exception as exc:
        fail(f"Failed to initialize faster-whisper model: {exc}")

    try:
        segments_iter, info = model.transcribe(
            str(wav_path),
            language=language_hint,
            beam_size=mode_config.beam_size,
            best_of=mode_config.best_of,
            condition_on_previous_text=mode_config.condition_on_previous_text,
            vad_filter=mode_config.vad_filter,
            vad_parameters=mode_config.vad_parameters if mode_config.vad_parameters else None,
            chunk_length=mode_config.chunk_length,
            no_speech_threshold=mode_config.no_speech_threshold,
            word_timestamps=False,
        )
    except Exception as exc:
        fail(f"ASR transcription failed: {exc}")

    segments: list[dict[str, float | str]] = []
    text_chunks: list[str] = []
    for segment in segments_iter:
        text = segment.text.strip()
        if not text:
            continue
        segments.append({
            "start": float(segment.start),
            "end": float(segment.end),
            "text": text,
        })
        text_chunks.append(text)

    elapsed = time.time() - t0
    print(f"  faster-whisper: transcription completed in {elapsed:.1f}s")

    raw_text = "\n".join(text_chunks).strip()
    if not raw_text:
        fail("Transcription produced an empty transcript")

    language_hint = (getattr(info, "language", None) or "").strip() or infer_language(
        normalize_lines(raw_text)
    )
    return RawTranscript(language=language_hint, raw_text=raw_text, segments=segments)


def transcribe_audio(mode_config: ModeConfig, wav_path: Path, language_hint: str | None = None) -> RawTranscript:
    if mode_config.backend == "mlx":
        return transcribe_audio_mlx(mode_config, wav_path, language_hint)
    return transcribe_audio_faster_whisper(mode_config, wav_path, language_hint)


# ---------------------------------------------------------------------------
# LLM Proofreading
# ---------------------------------------------------------------------------

LLM_MAX_RETRIES = 2
LLM_CHUNK_TIMEOUT = 180
LLM_LENGTH_TOLERANCE = 0.50


def _strip_llm_meta(text: str) -> str:
    """Strip meta-commentary lines that the LLM may prepend."""
    lines = text.strip().split("\n")
    meta_prefixes = ("以下是", "校对后", "修正后", "纠正后", "这是", "好的", "以下为", "校对结果")
    while lines and any(lines[0].strip().startswith(p) for p in meta_prefixes) and len(lines[0].strip()) < 40:
        lines.pop(0)
    return "\n".join(lines).strip()


def _clean_llm_punctuation(text: str) -> str:
    """Fix double-punctuation artifacts from LLM output."""
    text = re.sub(r",，", "，", text)
    text = re.sub(r"，,", "，", text)
    text = re.sub(r"\.。", "。", text)
    text = re.sub(r"。\.", "。", text)
    text = re.sub(r":，", "，", text)
    text = re.sub(r",\?", "？", text)
    return text


def _validate_llm_output(original: str, corrected: str) -> bool:
    """Reject LLM output that is clearly wrong."""
    if not corrected:
        return False
    orig_len = len(original)
    corr_len = len(corrected)
    if corr_len < orig_len * (1 - LLM_LENGTH_TOLERANCE) or corr_len > orig_len * (1 + LLM_LENGTH_TOLERANCE):
        return False
    return True


def _build_proofread_messages(
    chunk: str, context_summary: str = "", title_hint: str = "",
) -> list[dict[str, str]]:
    user_parts: list[str] = []
    if title_hint:
        user_parts.append(f"视频/音频标题（帮助判断领域和专有名词）：{title_hint}")
    if context_summary:
        user_parts.append(f"上文内容（供参考上下文，不需要校对）：\n{context_summary}")
    user_parts.append(f"待校对文本：\n{chunk}")
    return [
        {"role": "system", "content": LLM_PROOFREAD_PROMPT},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


# -- Backend: local (mlx-lm) ------------------------------------------------

def _load_local_llm(model_name: str) -> tuple:
    try:
        from mlx_lm import load
    except ImportError:
        fail("Required dependency not available: mlx-lm. Install with: pip install mlx-lm")
    print(f"  Loading local LLM: {model_name} ...")
    t0 = time.time()
    model, tokenizer = load(model_name)
    print(f"  Local LLM loaded in {time.time() - t0:.1f}s")
    return model, tokenizer


def _proofread_chunk_local(
    chunk: str, context_summary: str, title_hint: str,
    model: object, tokenizer: object,
) -> str:
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    messages = _build_proofread_messages(chunk, context_summary, title_hint)
    prompt = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False,
    )
    max_tokens = max(2048, int(len(chunk) * 2))
    sampler = make_sampler(temp=0.1)

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            response = generate(
                model, tokenizer, prompt=prompt,
                max_tokens=max_tokens, sampler=sampler,
            )
            corrected = _clean_llm_punctuation(_strip_llm_meta(response))
            if _validate_llm_output(chunk, corrected):
                return corrected
            print(f"(validation failed, ", end="")
            if attempt < LLM_MAX_RETRIES:
                print(f"retry {attempt + 1}) ", end="", flush=True)
                continue
            print("using original) ", end="")
        except Exception as exc:
            print(f"(error: {exc}) ", end="", flush=True)
            break
    return chunk


# -- Backend: claude CLI (fallback) -----------------------------------------

def _proofread_chunk_claude(
    chunk: str, context_summary: str, title_hint: str,
) -> str:
    messages = _build_proofread_messages(chunk, context_summary, title_hint)
    flat_prompt = messages[0]["content"] + "\n\n" + messages[1]["content"] + "\n\n校对后文本："

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                ["claude", "-p", flat_prompt],
                capture_output=True,
                text=True,
                timeout=LLM_CHUNK_TIMEOUT,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                print(f"(claude exit {result.returncode}: {stderr[:80]}, ", end="")
                if attempt < LLM_MAX_RETRIES:
                    print(f"retry {attempt + 1}) ", end="", flush=True)
                    continue
                print("using original) ", end="")
                break
            corrected = _clean_llm_punctuation(_strip_llm_meta(result.stdout))
            if _validate_llm_output(chunk, corrected):
                return corrected
            print(f"(validation failed, ", end="")
            if attempt < LLM_MAX_RETRIES:
                print(f"retry {attempt + 1}) ", end="", flush=True)
                continue
            print("using original) ", end="")
        except subprocess.TimeoutExpired:
            print(f"(timeout, ", end="")
            if attempt < LLM_MAX_RETRIES:
                print(f"retry {attempt + 1}) ", end="", flush=True)
                continue
            print("using original) ", end="")
        except Exception as exc:
            print(f"(error: {exc}, using original) ", end="", flush=True)
            break
    return chunk


# -- Orchestrator ------------------------------------------------------------

def llm_proofread_full(
    text: str, title_hint: str = "", backend: str = "local",
    llm_model: str | None = None, asr_mode: str = "balanced",
) -> str:
    """Split text into chunks and proofread each with the selected LLM backend."""
    lines = text.strip().split("\n")
    if not lines:
        return text

    CHUNK_SIZE = 2500
    CONTEXT_SIZE = 400
    MIN_TAIL_CHUNK = 500
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        current_chunk.append(line)
        current_len += len(line)
        if current_len >= CHUNK_SIZE:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
    if current_chunk:
        tail = "\n".join(current_chunk)
        if chunks and len(tail) < MIN_TAIL_CHUNK:
            chunks[-1] = chunks[-1] + "\n" + tail
        else:
            chunks.append(tail)
    if not chunks:
        return text

    # Pre-compute context summaries from original text (breaks sequential dependency)
    original_contexts: list[str] = [""]
    for i in range(len(chunks) - 1):
        ctx = chunks[i][-CONTEXT_SIZE:] if len(chunks[i]) > CONTEXT_SIZE else chunks[i]
        original_contexts.append(ctx)

    model_obj = tokenizer_obj = None
    if backend == "local":
        if llm_model:
            model_name = llm_model
        elif asr_mode == "fast":
            model_name = MLX_LLM_FAST_MODEL
        else:
            model_name = MLX_LLM_DEFAULT_MODEL
        model_obj, tokenizer_obj = _load_local_llm(model_name)
    elif backend == "claude":
        if not shutil.which("claude"):
            print("  WARNING: claude CLI not found, skipping LLM proofreading")
            return text

    print(f"  LLM proofreading ({backend}): {len(chunks)} chunks (~{CHUNK_SIZE} chars each)")
    t0 = time.time()
    proofread_chunks: list[str] = []

    for i, chunk in enumerate(chunks):
        print(f"    chunk {i + 1}/{len(chunks)} ({len(chunk)} chars) ...", end=" ", flush=True)

        if backend == "local":
            corrected = _proofread_chunk_local(
                chunk, original_contexts[i], title_hint, model_obj, tokenizer_obj,
            )
        else:
            corrected = _proofread_chunk_claude(chunk, original_contexts[i], title_hint)

        proofread_chunks.append(corrected)
        print("done")

    if model_obj is not None:
        del model_obj, tokenizer_obj
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    elapsed = time.time() - t0
    print(f"  LLM proofreading completed in {elapsed:.1f}s")
    return "\n".join(proofread_chunks)


# ---------------------------------------------------------------------------
# Text cleaning pipeline
# ---------------------------------------------------------------------------

def normalize_lines(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text.replace("\r\n", "\n"))
    lines = []
    for raw_line in normalized.splitlines():
        line = TIMESTAMP_RE.sub("", raw_line).strip()
        line = re.sub(r"\s+", " ", line)
        if line:
            lines.append(line)
    if not lines:
        fail("Transcript cleanup removed all content")
    return lines


def normalize_language_hint(language_hint: str | None) -> str | None:
    if not language_hint:
        return None
    lowered = language_hint.strip().lower()
    if lowered.startswith("zh"):
        return "zh"
    return "non-zh"


def infer_language(lines: list[str], language_hint: str | None = None) -> str:
    normalized_hint = normalize_language_hint(language_hint)
    if normalized_hint is not None:
        return normalized_hint
    joined = "".join(lines)
    chinese_chars = len(CHINESE_CHAR_RE.findall(joined))
    if chinese_chars >= max(20, len(joined) // 10):
        return "zh"
    return "non-zh"


def apply_replacements(text: str, replacements: dict[str, str]) -> str:
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def normalize_zh_punctuation(text: str) -> str:
    text = re.sub(r"(?<=[\u3400-\u9fff]),(?=[\u3400-\u9fff])", "，", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])\.(?=[\u3400-\u9fff])", "。", text)
    text = re.sub(r"《\s+", "《", text)
    text = re.sub(r"\s+》", "》", text)
    return text


def join_lines(lines: list[str], language: str) -> list[str]:
    sentences: list[str] = []
    current = ""
    terminal_re = re.compile(r"[。！？!?…]$") if language == "zh" else re.compile(r"[.!?…]$")
    soft_limit = 90 if language == "zh" else 180

    for line in lines:
        if language == "zh":
            if current:
                separator = "" if re.search(r"[，。！？；：]$", current) else "，"
                current = f"{current}{separator}{line}"
            else:
                current = line
        else:
            current = f"{current} {line}".strip() if current else line
        if terminal_re.search(line) or len(current) >= soft_limit:
            sentences.append(current.strip())
            current = ""
    if current:
        sentences.append(current.strip())
    return sentences


def paragraphize(sentences: list[str], language: str) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    current_len = 0
    paragraph_limit = 260 if language == "zh" else 700
    sentence_limit = 4 if language == "zh" else 5
    joiner = "" if language == "zh" else " "

    for sentence in sentences:
        current.append(sentence)
        current_len += len(sentence)
        if current_len >= paragraph_limit or len(current) >= sentence_limit:
            paragraph = joiner.join(current).strip()
            if language == "zh" and not re.search(r"[。！？!?…]$", paragraph):
                paragraph += "。"
            paragraphs.append(paragraph)
            current = []
            current_len = 0
    if current:
        paragraph = joiner.join(current).strip()
        if language == "zh" and not re.search(r"[。！？!?…]$", paragraph):
            paragraph += "。"
        paragraphs.append(paragraph)
    return "\n\n".join(paragraphs).strip() + "\n"


_CJK_STOPCHARS = set("的了是在和有这那我你他她它不也都就被把让比给对从要会能可还很着到过")


def _extract_cjk_names(text: str, min_len: int = 3, max_len: int = 4) -> dict[str, int]:
    """Extract potential CJK proper noun candidates (3-4 chars) and their frequencies."""
    from collections import Counter
    candidates: Counter[str] = Counter()
    for length in range(min_len, max_len + 1):
        for i in range(len(text) - length + 1):
            span = text[i:i + length]
            if (all(CHINESE_CHAR_RE.match(c) for c in span)
                    and not any(c in _CJK_STOPCHARS for c in span)):
                candidates[span] += 1
    return dict(candidates)


def unify_proper_nouns(text: str, threshold_ratio: float = 0.10) -> str:
    """Unify low-frequency variants of proper nouns to their high-frequency canonical form.

    Targets 3-4 char CJK names that share the same first character and differ by exactly
    one character (typical ASR variants of the same name). Filters out common words using
    a stopchar set.
    """
    name_counts = _extract_cjk_names(text, min_len=3, max_len=4)
    if not name_counts:
        return text

    MIN_CANONICAL_COUNT = 5
    MAX_VARIANT_COUNT = 4

    def _char_diff(a: str, b: str) -> int:
        if len(a) != len(b):
            return len(a) + len(b)
        return sum(1 for x, y in zip(a, b) if x != y)

    groups: dict[str, list[str]] = {}
    processed: set[str] = set()

    sorted_names = sorted(name_counts.items(), key=lambda x: -x[1])
    for canonical, count in sorted_names:
        if count < MIN_CANONICAL_COUNT or canonical in processed:
            continue
        group = [canonical]
        processed.add(canonical)
        for variant, vcount in sorted_names:
            if variant in processed or len(variant) != len(canonical):
                continue
            if (variant[0] == canonical[0]
                    and _char_diff(canonical, variant) == 1
                    and vcount <= MAX_VARIANT_COUNT
                    and vcount < count * threshold_ratio):
                group.append(variant)
                processed.add(variant)
        if len(group) > 1:
            groups[canonical] = group[1:]

    if not groups:
        return text

    replacements_applied = 0
    for canonical, variants in groups.items():
        for variant in variants:
            old_count = text.count(variant)
            if old_count > 0:
                text = text.replace(variant, canonical)
                replacements_applied += old_count
                print(f"  Proper noun unification: '{variant}'({old_count}) → '{canonical}'({name_counts[canonical]})")

    if replacements_applied:
        print(f"  Unified {replacements_applied} proper noun variant(s)")
    return text


def strip_trailing_garbage(text: str) -> str:
    """Remove repetitive trailing patterns commonly produced by ASR on credits/silence."""
    lines = text.rstrip().split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        words = last.split()
        if len(words) >= 4:
            unique = set(w.lower() for w in words)
            if len(unique) <= max(2, len(words) // 10):
                lines.pop()
                continue
        if len(last) < 10 and not re.search(r"[.!?。！？…]$", last):
            lines.pop()
            continue
        break
    return "\n".join(lines)


def clean_transcript(
    raw_text: str,
    raw_language_hint: str | None = None,
    llm_backend: str = "local",
    llm_model: str | None = None,
    title_hint: str = "",
    asr_mode: str = "balanced",
    extra_replacements: dict[str, str] | None = None,
    llm_proofread_en: bool = False,
) -> tuple[str, str]:
    lines = normalize_lines(raw_text)
    language = infer_language(lines, raw_language_hint)
    joined_text = "\n".join(lines)

    replacements = dict(ZH_REPLACEMENTS)
    if extra_replacements:
        replacements.update(extra_replacements)

    if language == "zh":
        joined_text = OpenCC("t2s").convert(joined_text)
        joined_text = apply_replacements(joined_text, replacements)
        joined_text = normalize_zh_punctuation(joined_text)

        if llm_backend != "none":
            print("  Running LLM proofreading for Chinese transcript ...")
            joined_text = llm_proofread_full(
                joined_text, title_hint=title_hint,
                backend=llm_backend, llm_model=llm_model,
                asr_mode=asr_mode,
            )
            joined_text = apply_replacements(joined_text, replacements)
            joined_text = normalize_zh_punctuation(joined_text)
        joined_text = unify_proper_nouns(joined_text)
    else:
        joined_text = apply_replacements(joined_text, EN_REPLACEMENTS)
        if llm_proofread_en and llm_backend != "none":
            print("  Running LLM proofreading for English transcript ...")
            joined_text = llm_proofread_full(
                joined_text, title_hint=title_hint,
                backend=llm_backend, llm_model=llm_model,
                asr_mode=asr_mode,
            )

    joined_text = strip_trailing_garbage(joined_text)
    cleaned_lines = normalize_lines(joined_text)
    sentences = join_lines(cleaned_lines, language)
    final_text = paragraphize(sentences, language)
    if language == "zh":
        final_text = normalize_zh_punctuation(final_text)
    return language, final_text


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def split_paragraphs(final_text: str) -> list[str]:
    return [p.strip() for p in final_text.strip().split("\n\n") if p.strip()]


def write_txt_output(final_text: str, output_path: Path) -> None:
    output_path.write_text(final_text, encoding="utf-8")


def ensure_pdf_font(language: str) -> str:
    if language != "zh":
        return "Helvetica"
    if PDF_CJK_FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return PDF_CJK_FONT_NAME
    for font_path in PDF_CJK_FONT_CANDIDATES:
        if not font_path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(PDF_CJK_FONT_NAME, str(font_path)))
            return PDF_CJK_FONT_NAME
        except Exception:
            continue
    fail(
        "No supported Chinese PDF font found. Tried: "
        + ", ".join(str(p) for p in PDF_CJK_FONT_CANDIDATES)
    )


def build_pdf_style(language: str) -> ParagraphStyle:
    styles = getSampleStyleSheet()
    font_name = ensure_pdf_font(language)
    return ParagraphStyle(
        "TranscriptBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=16 if language == "zh" else 14,
    )


def write_pdf_output(final_text: str, output_path: Path, input_path: Path, language: str) -> None:
    body_style = build_pdf_style(language)
    doc = SimpleDocTemplate(str(output_path), pagesize=LETTER)
    story = []
    for paragraph in split_paragraphs(final_text):
        story.append(Paragraph(escape(paragraph), body_style))
        story.append(Spacer(1, 10))
    doc.build(story)


def write_docx_output(final_text: str, output_path: Path, input_path: Path, language: str) -> None:
    document = Document()
    for paragraph in split_paragraphs(final_text):
        document.add_paragraph(paragraph)
    document.save(output_path)


def write_final_outputs(
    final_text: str, output_paths: dict[str, Path], input_path: Path, language: str,
) -> None:
    for fmt, output_path in output_paths.items():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "txt":
            write_txt_output(final_text, output_path)
        elif fmt == "pdf":
            write_pdf_output(final_text, output_path, input_path, language)
        elif fmt == "docx":
            write_docx_output(final_text, output_path, input_path, language)
        else:
            fail(f"Unsupported output format: {fmt}")


def maybe_preserve_debug_artifacts(
    keep_temp: bool, output_paths: dict[str, Path], audio_cache_path: Path, raw_cache_path: Path,
) -> None:
    if not keep_temp:
        return
    first_output = next(iter(output_paths.values()))
    debug_dir = first_output.parent / f"{first_output.stem}-debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    if "wav" in DEFAULT_KEEP_TEMP_ARTIFACTS and audio_cache_path.exists():
        shutil.copy2(audio_cache_path, debug_dir / audio_cache_path.name)
    if "raw.json" in DEFAULT_KEEP_TEMP_ARTIFACTS and raw_cache_path.exists():
        shutil.copy2(raw_cache_path, debug_dir / raw_cache_path.name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    total_t0 = time.time()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        fail(f"Input media file does not exist: {input_path}")
    if not input_path.is_file():
        fail(f"Input path is not a file: {input_path}")

    ffmpeg = require_command("ffmpeg")
    formats = normalize_formats(args.formats)
    mode_config = resolve_mode_config(args.mode, args.backend, args.model_path)
    llm_backend = "none" if args.no_llm_proofread else args.llm_backend
    llm_model = args.llm_model
    llm_proofread_en = args.llm_proofread_en
    language_hint = args.language.strip().lower() if args.language else None
    output_paths = resolve_output_paths(input_path, args.output, args.output_dir, formats)
    for output_path in output_paths.values():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    audio_cache_path = resolve_audio_cache_path(input_path)
    raw_cache_path = resolve_raw_cache_path(input_path, mode_config)
    raw_cache = None if args.force_transcribe else load_raw_transcript_cache(raw_cache_path)
    audio_cache_status = "skipped"

    if raw_cache is not None:
        raw_status = "hit"
        raw_transcript = raw_cache
    else:
        print("Step 1: Extracting audio ...")
        audio_cache_path, audio_cache_status = ensure_audio_cache(ffmpeg, input_path, audio_cache_path)
        print(f"  Audio cache: {audio_cache_status}")
        print("Step 2: Transcribing with ASR ...")
        raw_transcript = transcribe_audio(mode_config, audio_cache_path, language_hint)
        save_raw_transcript_cache(raw_cache_path, raw_transcript)
        raw_status = "miss"

    llm_enabled = llm_backend != "none"
    clean_cache_path = resolve_clean_cache_path(
        input_path, raw_transcript.raw_text, raw_transcript.language, llm_enabled
    )
    clean_cache = None if args.force_transcribe else load_clean_transcript_cache(clean_cache_path)
    if clean_cache is not None:
        language, final_text = clean_cache
        clean_status = "hit"
    else:
        import gc
        gc.collect()

        title_hint = input_path.stem
        extra_replacements = None
        if args.replacements_file:
            rpath = Path(args.replacements_file).expanduser().resolve()
            if rpath.exists():
                raw = json.loads(rpath.read_text(encoding="utf-8"))
                extra_replacements = {k: v for k, v in raw.items() if not k.startswith("_")}
                print(f"  Loaded {len(extra_replacements)} extra replacements from {rpath}")
            else:
                print(f"  WARNING: replacements file not found: {rpath}")
        print("Step 3: Cleaning and proofreading transcript ...")
        language, final_text = clean_transcript(
            raw_transcript.raw_text, raw_transcript.language,
            llm_backend=llm_backend, llm_model=llm_model, title_hint=title_hint,
            asr_mode=mode_config.name, extra_replacements=extra_replacements,
            llm_proofread_en=llm_proofread_en,
        )
        save_clean_transcript_cache(clean_cache_path, language, final_text)
        clean_status = "miss"

    print("Step 4: Writing output files ...")
    write_final_outputs(final_text, output_paths, input_path, language)
    maybe_preserve_debug_artifacts(args.keep_temp, output_paths, audio_cache_path, raw_cache_path)

    total_elapsed = time.time() - total_t0

    print(f"\nInput file: {input_path}")
    print(f"Inferred language: {language}")
    print(f"ASR backend: {mode_config.backend}")
    print(f"Mode: {mode_config.name}")
    print(f"ASR model: {mode_config.model_ref}")
    print(f"LLM proofreading: {llm_backend}" + (f" ({llm_model or MLX_LLM_DEFAULT_MODEL})" if llm_backend == "local" else ""))
    print("Cache status:")
    print(f"  audio: {audio_cache_status}")
    print(f"  raw-asr: {raw_status}")
    print(f"  cleaned-transcript: {clean_status}")
    print("Final output paths:")
    for fmt, output_path in output_paths.items():
        print(f"  {fmt}: {output_path}")
    print(f"Total time: {total_elapsed:.1f}s")
    print("Cleaned transcript: yes")


if __name__ == "__main__":
    main()
