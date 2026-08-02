#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   # MLX is Apple-Silicon only. Without these markers `uv run` tries to resolve
#   # them on Linux/Windows/Intel Mac, where they do not exist — contradicting
#   # the platform table in SKILL.md.
#   "mlx-whisper>=0.4.0; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   "mlx-lm>=0.22.0; sys_platform == 'darwin' and platform_machine == 'arm64'",
#   # Installs everywhere; it is the CPU fallback backend and also useful on Mac.
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
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

try:
    from opencc import OpenCC as OpenCCConverter
except ImportError:
    OpenCCConverter = None


PDF_CJK_FONT_CANDIDATES = [
    Path("/System/Library/Fonts/STHeiti Light.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Songti.ttc"),
]
PDF_CJK_FONT_NAME = "LocalTranscriptCJK"
MODEL_DOWNLOAD_ROOT = Path(
    os.environ.get("LOCAL_TRANSCRIPT_MODELS", "/tmp/local-transcript/models")
).expanduser()
# Hardcoding an absolute path leaves no recourse where /tmp is not writable
# (sandboxes, locked-down CI, shared hosts). The default is unchanged.
CACHE_ROOT = Path(
    os.environ.get("LOCAL_TRANSCRIPT_CACHE", "/tmp/local-transcript/cache")
).expanduser()
AUDIO_CACHE_VERSION = "2026-03-14-v3"
RAW_TRANSCRIPT_CACHE_VERSION = "2026-03-14-v3"
CLEAN_TRANSCRIPT_CACHE_VERSION = "2026-03-14-v11"
# Bump when the proofreading prompt changes: cached cleaned text produced by an
# older prompt is not interchangeable with new output.
PROOFREAD_PROMPT_VERSION = "1"

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


class _NoOpOpenCC:
    def convert(self, text: str) -> str:
        return text


def build_opencc_converter() -> object:
    if OpenCCConverter is None:
        return _NoOpOpenCC()
    return OpenCCConverter("t2s")


def save_minimal_docx(paragraphs: list[str], output_path: Path) -> None:
    document_xml = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">',
        "<w:body>",
    ]
    for paragraph in paragraphs:
        text = escape(paragraph)
        document_xml.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>")
    document_xml.extend(["<w:sectPr/>", "</w:body>", "</w:document>"])

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as docx_zip:
        docx_zip.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
""",
        )
        docx_zip.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
""",
        )
        docx_zip.writestr("word/document.xml", "\n".join(document_xml))

_EMBEDDED_ZH_REPLACEMENTS = {
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


def _load_zh_replacements() -> dict[str, str]:
    """Sidecar JSON is the source of truth; the embedded table is the fallback.

    The two used to be maintained separately and drifted. Loading the file when
    it is present makes divergence impossible; keeping the embedded copy means
    the script still works when copied out on its own.
    """
    sidecar = Path(__file__).resolve().parent / "zh_replacements.json"
    if sidecar.exists():
        try:
            raw = json.loads(sidecar.read_text(encoding="utf-8"))
            loaded = {k: v for k, v in raw.items() if not k.startswith("_")}
            if loaded:
                return loaded
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_EMBEDDED_ZH_REPLACEMENTS)


ZH_REPLACEMENTS = _load_zh_replacements()

# Derived from the table's contents, so it can never disagree with it.
BUILTIN_REPLACEMENTS_VERSION = hashlib.sha256(
    json.dumps(ZH_REPLACEMENTS, ensure_ascii=False, sort_keys=True).encode("utf-8")
).hexdigest()[:12]

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
        default="none",
        help="LLM backend for proofreading. Defaults to 'none' — the pass is opt-in "
             "(see SKILL.md 'LLM Proofreading Is Opt-In'). 'local' uses mlx-lm + "
             "Qwen2.5 on Apple Silicon; 'claude' uses the claude CLI.",
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
        "--emit-raw-asr",
        metavar="PATH",
        help="Also write the untouched ASR output (before OpenCC, replacements, "
             "punctuation normalisation and re-segmentation). Use this for a true "
             "raw baseline; --no-llm-proofread still produces cleaned text.",
    )
    parser.add_argument(
        "--unify-names",
        action="store_true",
        help="Enable the frequency-based Chinese proper-noun unification pass. "
             "OFF by default: it is a character-frequency heuristic with no lexicon, "
             "so a legitimate low-frequency word can be rewritten into a frequent "
             "one it happens to differ from by a single character "
             "(e.g. 苹果醋 -> 苹果汁). Review the run log when you enable it.",
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
    """Identify the media well enough that a swapped file cannot reuse its cache.

    Path + size + whole-second mtime collided when a file was replaced within the
    same second by content of the same length — plausible for generated or
    re-encoded media. Nanosecond mtime plus a sample of the head, middle and tail
    closes that without reading a multi-gigabyte file: an edit that preserves
    size, nanosecond timestamp AND all three sampled windows is not something
    that happens by accident.
    """
    stat = input_path.stat()
    digest = hashlib.sha256()
    digest.update(f"{input_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8"))
    window = 64 * 1024
    try:
        with open(input_path, "rb") as handle:
            digest.update(handle.read(window))
            if stat.st_size > window * 2:
                handle.seek(max(0, stat.st_size // 2 - window // 2))
                digest.update(handle.read(window))
                handle.seek(max(0, stat.st_size - window))
                digest.update(handle.read(window))
    except OSError:
        # Unreadable media is the transcriber's problem to report, not the
        # fingerprint's; fall back to metadata alone.
        pass
    return digest.hexdigest()


def resolve_audio_cache_path(input_path: Path) -> Path:
    media_key = resolve_media_fingerprint(input_path)
    cache_key = hashlib.sha256(f"{AUDIO_CACHE_VERSION}|{media_key}".encode("utf-8")).hexdigest()
    return CACHE_ROOT / "audio" / f"{cache_key}.wav"


def resolve_raw_cache_path(
    input_path: Path, mode_config: ModeConfig, language_hint: str | None = None
) -> Path:
    """Key the raw ASR cache on everything that changes the transcript.

    `--language` is part of that: transcribing the same file with `--language ja`
    after an auto-detected run must not silently return the first result. The
    hint is passed to the decoder, so it belongs in the identity.
    """
    media_key = resolve_media_fingerprint(input_path)
    language_key = (language_hint or "auto").strip().lower()
    cache_key = hashlib.sha256(
        f"{RAW_TRANSCRIPT_CACHE_VERSION}|{media_key}|{build_mode_identity(mode_config)}"
        f"|lang={language_key}".encode("utf-8")
    ).hexdigest()
    return CACHE_ROOT / "raw" / f"{cache_key}.json"


def build_clean_identity(
    llm_backend: str,
    llm_model: str | None,
    llm_proofread_en: bool,
    asr_mode: str,
    extra_replacements: dict[str, str] | None,
) -> str:
    """Everything that changes the cleaned text, as a stable string.

    A boolean "was an LLM involved" is not enough. Every one of these changes the
    output while leaving that boolean identical, so omitting any of them returns a
    stale transcript that looks correct:

    * backend (`local` vs `claude`) and the specific model;
    * `--llm-proofread-en` — for an English file the backend is unchanged, only
      this flag decides whether proofreading runs at all;
    * `asr_mode`, because it selects the 3B model in `fast` and the 7B model
      otherwise;
    * the contents of a `--replacements-file`, not merely its path.
    """
    effective_model = llm_model or (
        MLX_LLM_FAST_MODEL if asr_mode == "fast" else MLX_LLM_DEFAULT_MODEL
    )
    replacements_key = "none"
    if extra_replacements:
        payload = json.dumps(extra_replacements, ensure_ascii=False, sort_keys=True)
        replacements_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return "|".join([
        f"backend={llm_backend}",
        f"model={effective_model if llm_backend == 'local' else llm_backend}",
        f"proofread_en={int(bool(llm_proofread_en))}",
        f"asr_mode={asr_mode}",
        f"prompt={PROOFREAD_PROMPT_VERSION}",
        f"replacements={replacements_key}",
        f"builtin_zh={BUILTIN_REPLACEMENTS_VERSION}",
    ])


def resolve_clean_cache_path(
    input_path: Path,
    raw_text: str,
    language_hint: str | None,
    clean_identity: str,
) -> Path:
    media_key = resolve_media_fingerprint(input_path)
    raw_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    language_key = (language_hint or "auto").strip().lower()
    cache_key = hashlib.sha256(
        f"{CLEAN_TRANSCRIPT_CACHE_VERSION}|{media_key}|{raw_hash}|{language_key}"
        f"|{clean_identity}".encode("utf-8")
    ).hexdigest()
    return CACHE_ROOT / "clean" / f"{cache_key}.json"


def load_raw_transcript_cache(cache_path: Path) -> RawTranscript | None:
    data = _read_cache_json(cache_path)
    if data is None:
        return None
    language = data.get("language")
    raw_text = data.get("raw_text")
    segments = data.get("segments")
    if not language or not raw_text or not isinstance(segments, list):
        return None
    return RawTranscript(language=language, raw_text=raw_text, segments=segments)


def _is_complete_wav(path: Path) -> bool:
    """A non-empty file is not a finished WAV.

    ffmpeg killed mid-extraction leaves bytes on disk that pass a size check and
    then feed a truncated waveform to the ASR. Validate the RIFF/WAVE header and
    that the declared chunk size roughly matches what is on disk.
    """
    try:
        size = path.stat().st_size
        if size < 44:  # smaller than a WAV header
            return False
        with open(path, "rb") as handle:
            header = handle.read(12)
        if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            return False
        declared = int.from_bytes(header[4:8], "little") + 8
        return declared <= size
    except OSError:
        return False


def _atomic_write_text(path: Path, payload: str) -> None:
    """Write via a temp file in the same directory, then rename.

    `write_text` leaves a truncated file behind when the process dies mid-write,
    and the next run reads it as a valid cache. `os.replace` is atomic within a
    filesystem, so a reader sees either the old file or the complete new one.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _read_cache_json(cache_path: Path) -> dict | None:
    """Corrupt or unreadable cache is a miss, not a crash."""
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        print(f"  WARNING: discarding corrupt cache file {cache_path.name}")
        cache_path.unlink(missing_ok=True)
        return None
    return data if isinstance(data, dict) else None


def save_raw_transcript_cache(cache_path: Path, transcript: RawTranscript) -> None:
    _atomic_write_text(cache_path, json.dumps(asdict(transcript), ensure_ascii=False))


def load_clean_transcript_cache(cache_path: Path) -> tuple[str, str] | None:
    data = _read_cache_json(cache_path)
    if data is None:
        return None
    language = data.get("language")
    final_text = data.get("final_text")
    if not language or not final_text:
        return None
    return language, final_text


def save_clean_transcript_cache(cache_path: Path, language: str, final_text: str) -> None:
    _atomic_write_text(
        cache_path,
        json.dumps({"language": language, "final_text": final_text}, ensure_ascii=False),
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
    if audio_cache_path.exists() and _is_complete_wav(audio_cache_path):
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
        # `beam_size` and `best_of` reach DecodingOptions through
        # transcribe(**decode_options). Without them `accurate` decoded exactly
        # like `balanced` — same model, greedy search — and differed only in its
        # cache key, while SKILL.md promised a higher beam size.
        # beam_size applies at temperature 0; best_of covers the temperature
        # fallbacks, so both are needed for the setting to hold across retries.
        decode_options: dict[str, object] = {}
        if mode_config.beam_size and mode_config.beam_size > 1:
            decode_options["beam_size"] = mode_config.beam_size
            decode_options["best_of"] = max(mode_config.beam_size, mode_config.best_of)
        elif mode_config.best_of and mode_config.best_of > 1:
            decode_options["best_of"] = mode_config.best_of
        if decode_options:
            print(f"  mlx-whisper: decoding with {decode_options}")

        result = mlx_whisper.transcribe(
            str(wav_path),
            path_or_hf_repo=mode_config.model_ref,
            language=language_hint,
            word_timestamps=False,
            fp16=True,
            condition_on_previous_text=False,
            **decode_options,
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
# A proofread may reflow lines but must not dissolve the paragraph structure.
LLM_MIN_LINE_RATIO = 0.5
# Three identical substantial lines in a row is a decode loop, not prose.
LLM_MAX_REPEAT_RUN = 3
LLM_LENGTH_TOLERANCE = 0.50
# How far a paragraph may overflow its soft limit while waiting for a sentence
# to end, before it is cut regardless. Whisper's Chinese output carries almost
# no sentence terminators (5 in a 10k-character transcript), so an unbounded
# wait would produce 600-character paragraphs; 1.25 keeps the layout close to
# the 260-character target while still letting a nearby sentence finish.
PARAGRAPH_HARD_RATIO = 1.25


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


# Openers an instruction-tuned model emits when it answers *about* the task
# instead of performing it. Their presence means the chunk was not proofread.
_LLM_META_PREFIXES = (
    "以下是校对", "以下是修正", "以下为校对", "校对后的", "修正后的",
    "here is the corrected", "here's the corrected", "corrected text:",
    "sure,", "certainly,", "好的，",
)

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")

# Field labels used in _build_proofread_messages. Echoed back, they mean the
# model reproduced the prompt instead of answering it.
_LLM_PROMPT_LABELS = ("待校对文本", "上文内容（供参考上下文", "视频/音频标题")


def _repetition_run(text: str) -> int:
    """Longest run of an identical non-trivial line — the classic decode loop."""
    lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 8]
    longest = run = 0
    previous = None
    for line in lines:
        run = run + 1 if line == previous else 1
        previous = line
        longest = max(longest, run)
    return longest


def _validate_llm_output(original: str, corrected: str) -> tuple[bool, str]:
    """Reject LLM output that is clearly not a faithful proofread.

    A length check alone cannot see hallucination, dropped paragraphs, decode
    loops or invented figures — all of which keep the length roughly intact. For
    a transcript a confident rewrite is more damaging than a surviving ASR typo,
    so each failure mode gets its own test and its own reason string.
    """
    if not corrected:
        return False, "empty output"

    orig_len, corr_len = len(original), len(corrected)
    if corr_len < orig_len * (1 - LLM_LENGTH_TOLERANCE):
        return False, f"output too short ({corr_len} vs {orig_len} chars)"
    if corr_len > orig_len * (1 + LLM_LENGTH_TOLERANCE):
        return False, f"output too long ({corr_len} vs {orig_len} chars)"

    head = corrected.lstrip()[:40].lower()
    for prefix in _LLM_META_PREFIXES:
        if head.startswith(prefix):
            return False, f"model answered about the task instead of doing it: {prefix!r}"

    orig_lines = len([ln for ln in original.splitlines() if ln.strip()])
    corr_lines = len([ln for ln in corrected.splitlines() if ln.strip()])
    if orig_lines >= 4 and corr_lines < orig_lines * LLM_MIN_LINE_RATIO:
        return False, f"line structure collapsed ({corr_lines} vs {orig_lines} lines)"

    # The prompt's own field labels must never surface in the answer. Only
    # flag a label the source did not already contain, so a transcript that
    # genuinely says these words is not rejected for quoting itself.
    for label in _LLM_PROMPT_LABELS:
        if label in corrected and label not in original:
            return False, f"echoed the prompt label {label!r} into the text"

    run = _repetition_run(corrected)
    if run >= LLM_MAX_REPEAT_RUN:
        return False, f"repeated the same line {run} times (decode loop)"

    # Numbers must not be invented. Dropping one can happen when ASR duplicated
    # it; conjuring one that was never spoken is hallucination.
    invented = set(_NUMBER_RE.findall(corrected)) - set(_NUMBER_RE.findall(original))
    if invented:
        return False, f"introduced numbers not present in the source: {sorted(invented)[:5]}"

    return True, ""


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
            accepted, reason = _validate_llm_output(chunk, corrected)
            if accepted:
                return corrected
            print(f"(rejected: {reason}, ", end="")
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
            accepted, reason = _validate_llm_output(chunk, corrected)
            if accepted:
                return corrected
            print(f"(rejected: {reason}, ", end="")
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
            # Returning the text unchanged used to look like a successful
            # proofread: the run reported "LLM proofreading: claude" and the
            # result was cached under the claude identity, so installing the CLI
            # later hit that un-proofread cache. Fail instead of degrading.
            fail(
                "LLM backend 'claude' was requested but the claude CLI is not on PATH. "
                "Install it, choose --llm-backend local, or pass --no-llm-proofread "
                "to skip proofreading deliberately."
            )

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
    # A halfwidth comma after a CJK character is a Chinese comma whatever
    # follows it. The old both-sides lookaround only fired between two CJK
    # characters, so it skipped ",Palantir" and — worse — the ",，" pair,
    # because U+FF0C sits outside the range the lookahead demanded.
    text = re.sub(r"(?<=[\u3400-\u9fff]),", "，", text)
    text = re.sub(r"(?<=[\u3400-\u9fff])\.(?=[\u3400-\u9fff])", "。", text)
    # Collapse duplicates left behind by a mixed-width join. Repeated
    # full-width punctuation is never intentional in a transcript.
    text = re.sub(r"，{2,}", "，", text)
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"[，、]。", "。", text)
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
                # Halfwidth marks count as punctuation too: without them a
                # line ending in "," was treated as unpunctuated and got a
                # second, full-width comma appended — the ",，" artifact.
                separator = "" if re.search(r"[，。！？；：、,.!?;:]$", current) else "，"
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
    """Group sentences into paragraphs, breaking only where one ends.

    The length limit is a target, not a guillotine. Cutting between two
    clauses and stamping a period on the stump fabricates a sentence
    boundary the speaker never uttered and leaves the next paragraph
    opening mid-thought, so overflow past the soft limit until the text
    actually terminates. HARD_RATIO bounds the overflow for input that
    never terminates at all.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    current_len = 0
    paragraph_limit = 260 if language == "zh" else 700
    sentence_limit = 4 if language == "zh" else 5
    hard_limit = paragraph_limit * PARAGRAPH_HARD_RATIO
    joiner = "" if language == "zh" else " "
    terminal_re = (
        re.compile(r"[。！？!?…]$") if language == "zh" else re.compile(r"[.!?…]$")
    )

    for sentence in sentences:
        current.append(sentence)
        current_len += len(sentence)
        reached = current_len >= paragraph_limit or len(current) >= sentence_limit
        ends_sentence = bool(terminal_re.search(current[-1].strip()))
        if (reached and ends_sentence) or current_len >= hard_limit:
            paragraphs.append(joiner.join(current).strip())
            current = []
            current_len = 0
    if current:
        paragraphs.append(joiner.join(current).strip())
    # Only the very last paragraph may be given a terminator: the document
    # ends there, so nothing is being split in two.
    if paragraphs and language == "zh" and not re.search(r"[。！？!?…]$", paragraphs[-1]):
        paragraphs[-1] += "。"
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


def unify_proper_nouns(
    text: str, threshold_ratio: float = 0.10
) -> tuple[str, list[tuple[str, str, int]]]:
    """Unify low-frequency variants of proper nouns to their high-frequency form.

    Returns `(text, applied)` where `applied` is `[(variant, canonical, count)]`.

    OFF BY DEFAULT — enable with `--unify-names`.

    HEURISTIC, NOT ENTITY RECOGNITION. This slides a character window over the
    text and groups by frequency; it has no lexicon and cannot tell a person's
    name from an ordinary phrase. Any legitimate low-frequency word that differs
    from a frequent one by a single character is rewritten: with 11 occurrences
    of 苹果汁 and one of 苹果醋 the cider becomes juice. That is a deterministic
    change of meaning, which is why the pass no longer runs unless asked for.

    The guards below narrow the damage but cannot remove it — same length, same
    first character and a frequency gap describe real distinct words as readily
    as they describe ASR variants:

    * a variant that is part of a longer frequent span is skipped, so an
      overlapping window cannot swallow the phrase containing it;
    * the canonical form must dominate — see MIN_CANONICAL_COUNT and
      threshold_ratio — and every substitution is printed, so a wrong one is
      visible in the run log rather than silent.
    """
    name_counts = _extract_cjk_names(text, min_len=3, max_len=4)
    if not name_counts:
        return text, []

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
        return text, []

    def _is_nested_in_frequent_span(candidate: str) -> bool:
        """True when the candidate only ever occurs inside a longer frequent span.

        Without this the window that produced a 3-char slice of a 4-char name
        competes with the name itself, and rewriting the slice corrupts the
        surrounding phrase.
        """
        for other, other_count in name_counts.items():
            if other != candidate and candidate in other and other_count >= MIN_CANONICAL_COUNT:
                return True
        return False

    applied: list[tuple[str, str, int]] = []
    for canonical, variants in groups.items():
        for variant in variants:
            if _is_nested_in_frequent_span(variant):
                print(f"  Proper noun unification: skipped '{variant}' (part of a longer frequent span)")
                continue
            old_count = text.count(variant)
            if old_count > 0:
                text = text.replace(variant, canonical)
                applied.append((variant, canonical, old_count))
                print(f"  Proper noun unification: '{variant}'({old_count}) → '{canonical}'({name_counts[canonical]})")

    if applied:
        total = sum(count for _, _, count in applied)
        print(f"  Unified {total} proper noun occurrence(s) across {len(applied)} variant(s)")
    return text, applied


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
    llm_backend: str = "none",
    llm_model: str | None = None,
    title_hint: str = "",
    asr_mode: str = "balanced",
    extra_replacements: dict[str, str] | None = None,
    llm_proofread_en: bool = False,
    unify_names: bool = False,
) -> tuple[str, str]:
    lines = normalize_lines(raw_text)
    language = infer_language(lines, raw_language_hint)
    joined_text = "\n".join(lines)

    replacements = dict(ZH_REPLACEMENTS)
    if extra_replacements:
        replacements.update(extra_replacements)

    if language == "zh":
        joined_text = build_opencc_converter().convert(joined_text)
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
        if unify_names:
            joined_text, _ = unify_proper_nouns(joined_text)
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
    if DocxDocument is None:
        save_minimal_docx(split_paragraphs(final_text), output_path)
        return

    document = DocxDocument()
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
    raw_cache_path = resolve_raw_cache_path(input_path, mode_config, language_hint)
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

    # The replacements file is read BEFORE the cache lookup: its contents are
    # part of the cache identity, so resolving the key without them would let a
    # changed table return the previous cleaning.
    extra_replacements = None
    if args.replacements_file:
        rpath = Path(args.replacements_file).expanduser().resolve()
        if rpath.exists():
            raw = json.loads(rpath.read_text(encoding="utf-8"))
            extra_replacements = {k: v for k, v in raw.items() if not k.startswith("_")}
            print(f"  Loaded {len(extra_replacements)} extra replacements from {rpath}")
        else:
            print(f"  WARNING: replacements file not found: {rpath}")

    unify_names = args.unify_names
    clean_identity = build_clean_identity(
        llm_backend, llm_model, llm_proofread_en, mode_config.name, extra_replacements
    ) + f"|unify_names={int(unify_names)}"
    clean_cache_path = resolve_clean_cache_path(
        input_path, raw_transcript.raw_text, raw_transcript.language, clean_identity
    )
    clean_cache = None if args.force_transcribe else load_clean_transcript_cache(clean_cache_path)
    if clean_cache is not None:
        language, final_text = clean_cache
        clean_status = "hit"
    else:
        import gc
        gc.collect()

        title_hint = input_path.stem
        print("Step 3: Cleaning and proofreading transcript ...")
        language, final_text = clean_transcript(
            raw_transcript.raw_text, raw_transcript.language,
            llm_backend=llm_backend, llm_model=llm_model, title_hint=title_hint,
            asr_mode=mode_config.name, extra_replacements=extra_replacements,
            llm_proofread_en=llm_proofread_en, unify_names=unify_names,
        )
        save_clean_transcript_cache(clean_cache_path, language, final_text)
        clean_status = "miss"

    if args.emit_raw_asr:
        raw_out = Path(args.emit_raw_asr).expanduser().resolve()
        raw_out.parent.mkdir(parents=True, exist_ok=True)
        raw_out.write_text(raw_transcript.raw_text, encoding="utf-8")
        print(f"  Raw ASR text written to {raw_out}")

    print("Step 4: Writing output files ...")
    write_final_outputs(final_text, output_paths, input_path, language)
    maybe_preserve_debug_artifacts(args.keep_temp, output_paths, audio_cache_path, raw_cache_path)

    total_elapsed = time.time() - total_t0

    print(f"\nInput file: {input_path}")
    print(f"Inferred language: {language}")
    print(f"ASR backend: {mode_config.backend}")
    print(f"Mode: {mode_config.name}")
    print(f"ASR model: {mode_config.model_ref}")
    # Report what actually ran. Two earlier inaccuracies: the 7B default was
    # printed even in `fast` mode, which uses the 3B model, and the backend was
    # printed for English transcripts that were never proofread because
    # --llm-proofread-en was not given.
    proofread_ran = llm_backend != "none" and (language == "zh" or llm_proofread_en)
    if not proofread_ran:
        skip_reason = (
            "disabled" if llm_backend == "none"
            else "not enabled for English (pass --llm-proofread-en)"
        )
        print(f"LLM proofreading: none ({skip_reason})")
    elif llm_backend == "local":
        effective_model = llm_model or (
            MLX_LLM_FAST_MODEL if mode_config.name == "fast" else MLX_LLM_DEFAULT_MODEL
        )
        print(f"LLM proofreading: local ({effective_model})")
    else:
        print(f"LLM proofreading: {llm_backend}")
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
