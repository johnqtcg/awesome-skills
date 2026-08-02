import hashlib
import importlib.util
import re
import os
import json
from pathlib import Path
import subprocess
import sys

import pytest


def load_module():
    script_path = Path(__file__).resolve().parents[1] / "local_transcript.py"
    spec = importlib.util.spec_from_file_location("local_transcript", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_output_paths_defaults_to_txt():
    module = load_module()
    input_path = Path("/tmp/demo.mp4")

    output_paths = module.resolve_output_paths(
        input_path=input_path,
        output=None,
        output_dir=None,
        formats=["txt"],
    )

    assert output_paths == {
        "txt": Path("/tmp/demo-transcript.txt"),
    }


def test_resolve_output_paths_support_multiple_formats_in_output_dir(tmp_path):
    module = load_module()
    input_path = tmp_path / "clip.mkv"

    output_paths = module.resolve_output_paths(
        input_path=input_path,
        output=None,
        output_dir=str(tmp_path / "exports"),
        formats=["pdf", "docx", "txt"],
    )

    assert output_paths == {
        "pdf": tmp_path / "exports" / "clip-transcript.pdf",
        "docx": tmp_path / "exports" / "clip-transcript.docx",
        "txt": tmp_path / "exports" / "clip-transcript.txt",
    }


def test_resolve_output_paths_reject_multiple_formats_with_explicit_output(tmp_path, capsys):
    module = load_module()
    input_path = tmp_path / "clip.mkv"

    with pytest.raises(SystemExit):
        module.resolve_output_paths(
            input_path=input_path,
            output=str(tmp_path / "custom.out"),
            output_dir=None,
            formats=["txt", "pdf"],
        )
    captured = capsys.readouterr()
    assert "single output format" in captured.err


def test_resolve_mode_config_supports_mlx_and_faster_whisper_presets():
    module = load_module()

    fast_mlx = module.resolve_mode_config("fast", "mlx")
    balanced_fw = module.resolve_mode_config("balanced", "faster-whisper")
    accurate_fw = module.resolve_mode_config("accurate", "faster-whisper", "/tmp/ggml-medium.bin")

    assert fast_mlx.name == "fast"
    assert fast_mlx.backend == "mlx"
    assert fast_mlx.model_ref == module.MLX_MODEL_MAP["fast"]
    assert fast_mlx.compute_type == "float16"
    assert balanced_fw.backend == "faster-whisper"
    assert balanced_fw.condition_on_previous_text is False
    assert balanced_fw.vad_filter is True
    assert balanced_fw.num_workers >= 1
    assert accurate_fw.condition_on_previous_text is False
    assert accurate_fw.model_ref == "/tmp/ggml-medium.bin"
    assert accurate_fw.beam_size > balanced_fw.beam_size


def test_resolve_mode_config_supports_mlx_model_override():
    module = load_module()

    accurate_mlx = module.resolve_mode_config(
        "accurate", "mlx", "mlx-community/whisper-large-v3"
    )

    assert accurate_mlx.backend == "mlx"
    assert accurate_mlx.model_ref == "mlx-community/whisper-large-v3"
    assert accurate_mlx.beam_size == 5


def test_layered_cache_paths_are_distinct(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "CACHE_ROOT", tmp_path / "cache")

    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"video")
    mode_config = module.resolve_mode_config("balanced", "mlx")

    audio_path = module.resolve_audio_cache_path(input_path)
    raw_path = module.resolve_raw_cache_path(input_path, mode_config)
    clean_path = module.resolve_clean_cache_path(input_path, "raw text", "zh", True)
    clean_path_no_llm = module.resolve_clean_cache_path(input_path, "raw text", "zh", False)

    assert audio_path.suffix == ".wav"
    assert raw_path.suffix == ".json"
    assert clean_path.suffix == ".json"
    assert audio_path != raw_path
    assert raw_path != clean_path
    assert clean_path != clean_path_no_llm


def test_write_final_outputs_creates_all_requested_formats(tmp_path):
    module = load_module()
    output_paths = {
        "txt": tmp_path / "transcript.txt",
        "pdf": tmp_path / "transcript.pdf",
        "docx": tmp_path / "transcript.docx",
    }

    module.write_final_outputs(
        final_text="First paragraph.\n\nSecond paragraph.\n",
        output_paths=output_paths,
        input_path=Path("/tmp/example.mp4"),
        language="non-zh",
    )

    assert output_paths["txt"].read_text(encoding="utf-8") == "First paragraph.\n\nSecond paragraph.\n"
    assert output_paths["pdf"].read_bytes().startswith(b"%PDF")
    assert output_paths["docx"].read_bytes()[:2] == b"PK"


def test_ensure_pdf_font_registers_cjk_font_for_chinese():
    module = load_module()

    font_name = module.ensure_pdf_font("zh")

    assert font_name == module.PDF_CJK_FONT_NAME


def test_build_pdf_style_uses_uniform_body_size():
    module = load_module()

    body_style = module.build_pdf_style("zh")

    assert body_style.fontSize == 10.5


def test_write_pdf_output_uses_cjk_font_for_chinese(tmp_path):
    module = load_module()
    output_path = tmp_path / "zh.pdf"

    module.write_pdf_output(
        final_text="第一段内容。\n\n第二段内容。\n",
        output_path=output_path,
        input_path=Path("/tmp/example.mp4"),
        language="zh",
    )

    result = subprocess.run(
        ["pdffonts", str(output_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert any(token in result.stdout for token in ("STHeiti", "Songti"))


def test_clean_transcript_applies_high_confidence_zh_replacements():
    module = load_module()

    language, cleaned = module.clean_transcript(
        "奇外死亡\nV P N\nShadow socks\n",
        raw_language_hint="zh",
        llm_backend="none",
    )

    assert language == "zh"
    assert "奇怪死亡" in cleaned
    assert "VPN" in cleaned
    assert "Shadowsocks" in cleaned


def test_clean_transcript_uses_language_hint_for_short_chinese_text():
    module = load_module()

    language, cleaned = module.clean_transcript(
        "奇外死亡。\n",
        raw_language_hint="zh",
        llm_backend="none",
    )

    assert language == "zh"
    assert "奇怪死亡" in cleaned


def test_write_pdf_output_omits_metadata_header(tmp_path):
    module = load_module()
    output_path = tmp_path / "plain.pdf"

    module.write_pdf_output(
        final_text="第一段内容。\n\n第二段内容。\n",
        output_path=output_path,
        input_path=Path("/tmp/example.mp4"),
        language="zh",
    )

    result = subprocess.run(
        ["pdftotext", str(output_path), "-"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Transcript:" not in result.stdout
    assert "Inferred language:" not in result.stdout


def test_clean_transcript_runs_llm_proofread_when_enabled(monkeypatch):
    module = load_module()
    calls = {}

    def fake_llm_proofread_full(text, title_hint="", backend="local", llm_model=None, asr_mode="balanced"):
        calls["text"] = text
        calls["title_hint"] = title_hint
        calls["backend"] = backend
        calls["llm_model"] = llm_model
        calls["asr_mode"] = asr_mode
        return (
            "读懂了这本书你就看懂了今天国际政治舞台上最让人惊掉下巴的一个百年未有之大变局\n"
            "第一件事是2月份的慕尼黑安全会议\n"
            "几乎是在字里行间重新定义了欧洲的地位\n"
            "当时是全场死寂\n"
            "以美国副总统万斯为代表的这些美国保守主义势力\n"
            "这本书《欧洲的奇怪死亡》里的观点\n"
            "非常古典的哲学隐喻，忒修斯之船\n"
            "原封不动地照搬进了华盛顿的叙事里\n"
        )

    monkeypatch.setattr(module, "llm_proofread_full", fake_llm_proofread_full)

    language, cleaned = module.clean_transcript(
        "读懂了这本书你就看懂了今天国际政治舞台上最让人尽掉下巴的一个百年未有之大变局\n"
        "第一件事是2月份的莫尼黑安全会议\n"
        "几乎是在自理航间重新定义了欧洲的地位\n"
        "当时是全场死忌\n"
        "以美国副总统万思维代表的这些美国保守主义势力\n"
        "这本书欧洲的奇怪似王里的观点\n"
        "非常古典的哲学隐喻特休斯之喘\n"
        "原分不动的照搬进了华盛顿的叙事里\n",
        raw_language_hint="zh",
        llm_backend="local",
        title_hint="《欧洲的奇怪死亡》",
    )

    assert language == "zh"
    assert "最让人惊掉下巴的一个百年未有之大变局" in cleaned
    assert "2月份的慕尼黑安全会议" in cleaned
    assert "几乎是在字里行间重新定义了欧洲的地位" in cleaned
    assert "全场死寂" in cleaned
    assert "以美国副总统万斯为代表的" in cleaned
    assert "这本书《欧洲的奇怪死亡》里的观点" in cleaned
    assert "非常古典的哲学隐喻，忒修斯之船" in cleaned
    assert "原封不动地照搬进了华盛顿的叙事里" in cleaned
    assert calls == {
        "text": (
            "读懂了这本书你就看懂了今天国际政治舞台上最让人尽掉下巴的一个百年未有之大变局\n"
            "第一件事是2月份的莫尼黑安全会议\n"
            "几乎是在自理航间重新定义了欧洲的地位\n"
            "当时是全场死忌\n"
            "以美国副总统万思维代表的这些美国保守主义势力\n"
            "这本书欧洲的奇怪似王里的观点\n"
            "非常古典的哲学隐喻特休斯之喘\n"
            "原分不动的照搬进了华盛顿的叙事里"
        ),
        "title_hint": "《欧洲的奇怪死亡》",
        "backend": "local",
        "llm_model": None,
        "asr_mode": "balanced",
    }


def test_unify_proper_nouns_normalizes_low_frequency_variants():
    module = load_module()

    text = (
        "哈里斯发表讲话。\n"
        "哈里斯强调欧洲问题。\n"
        "哈里斯继续施压。\n"
        "哈里斯提出新要求。\n"
        "哈里斯主导这场争论。\n"
        "哈里斯再次回应。\n"
        "哈里斯继续定调。\n"
        "哈里斯强调联盟。\n"
        "哈里斯坚持立场。\n"
        "哈里斯出席会议。\n"
        "哈里斯接受采访。\n"
        "哈理斯也被提及一次。\n"
    )

    unified, applied = module.unify_proper_nouns(text)

    assert "哈理斯" not in unified
    assert unified.count("哈里斯") == 12
    assert applied == [("哈理斯", "哈里斯", 1)]


def test_raw_and_clean_transcript_cache_roundtrip(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "CACHE_ROOT", tmp_path / "cache")

    input_path = tmp_path / "clip.mp4"
    input_path.write_bytes(b"video")
    mode_config = module.resolve_mode_config("balanced", "mlx")

    raw_cache_path = module.resolve_raw_cache_path(input_path, mode_config)
    raw_transcript = module.RawTranscript(
        language="zh",
        raw_text="原始正文\n",
        segments=[{"start": 0.0, "end": 1.0, "text": "原始正文"}],
    )
    module.save_raw_transcript_cache(raw_cache_path, raw_transcript)

    loaded_raw = module.load_raw_transcript_cache(raw_cache_path)
    assert loaded_raw == raw_transcript

    clean_cache_path = module.resolve_clean_cache_path(
        input_path, raw_transcript.raw_text, raw_transcript.language, True
    )
    module.save_clean_transcript_cache(clean_cache_path, "zh", "清洗后正文\n")

    assert module.load_clean_transcript_cache(clean_cache_path) == ("zh", "清洗后正文\n")


@pytest.mark.parametrize("backend", ["mlx", "faster-whisper"])
def test_transcribe_audio_dispatches_to_selected_backend(monkeypatch, tmp_path, backend):
    module = load_module()
    wav_path = tmp_path / "audio.wav"
    wav_path.write_bytes(b"RIFF")
    calls = []

    def fake_mlx(mode_config, passed_wav_path, language_hint=None):
        calls.append(("mlx", mode_config.backend, passed_wav_path, language_hint))
        return module.RawTranscript("zh", "第一句\n第二句", [])

    def fake_fw(mode_config, passed_wav_path, language_hint=None):
        calls.append(("faster-whisper", mode_config.backend, passed_wav_path, language_hint))
        return module.RawTranscript("zh", "第一句\n第二句", [])

    monkeypatch.setattr(module, "transcribe_audio_mlx", fake_mlx)
    monkeypatch.setattr(module, "transcribe_audio_faster_whisper", fake_fw)
    mode_config = module.resolve_mode_config("balanced", backend)

    transcript = module.transcribe_audio(mode_config, wav_path, "zh")

    assert transcript.language == "zh"
    assert transcript.raw_text == "第一句\n第二句"
    assert calls == [(backend, backend, wav_path, "zh")]


# ---------------------------------------------------------------------------
# Cache identity: a stale hit here returns a plausible transcript produced under
# a different configuration, with nothing in the output to reveal it. These are
# the highest-severity tests in the file.
# ---------------------------------------------------------------------------

def _dummy_media(tmp_path):
    media = tmp_path / "clip.mp3"
    media.write_bytes(b"\x00" * 512)
    return media


def test_raw_cache_key_includes_language_hint(tmp_path):
    module = load_module()
    media = _dummy_media(tmp_path)
    config = module.resolve_mode_config("balanced", "mlx", None)
    auto = module.resolve_raw_cache_path(media, config, None)
    japanese = module.resolve_raw_cache_path(media, config, "ja")
    assert auto != japanese, (
        "transcribing with --language ja must not reuse the auto-detected result"
    )


def test_raw_cache_key_separates_modes(tmp_path):
    module = load_module()
    media = _dummy_media(tmp_path)
    balanced = module.resolve_mode_config("balanced", "mlx", None)
    accurate = module.resolve_mode_config("accurate", "mlx", None)
    assert module.resolve_raw_cache_path(media, balanced, None) != \
        module.resolve_raw_cache_path(media, accurate, None)


@pytest.mark.parametrize("changed", [
    {"llm_backend": "claude"},
    {"llm_model": "mlx-community/other-model"},
    {"llm_proofread_en": True},
    {"asr_mode": "fast"},
    {"extra_replacements": {"甲": "乙"}},
])
def test_clean_cache_identity_covers_every_output_changing_input(changed):
    """Each of these alters the cleaned text while leaving "an LLM ran" true."""
    module = load_module()
    base = dict(
        llm_backend="local", llm_model=None, llm_proofread_en=False,
        asr_mode="balanced", extra_replacements=None,
    )
    variant = {**base, **changed}
    assert module.build_clean_identity(**base) != module.build_clean_identity(**variant), (
        f"changing {list(changed)[0]} must change the clean cache identity"
    )


def test_clean_cache_identity_is_stable_for_identical_config():
    module = load_module()
    args = dict(
        llm_backend="local", llm_model=None, llm_proofread_en=True,
        asr_mode="balanced", extra_replacements={"甲": "乙"},
    )
    assert module.build_clean_identity(**args) == module.build_clean_identity(**args)


def test_replacements_identity_tracks_contents_not_just_presence():
    module = load_module()
    common = dict(llm_backend="local", llm_model=None, llm_proofread_en=False, asr_mode="balanced")
    one = module.build_clean_identity(**common, extra_replacements={"甲": "乙"})
    two = module.build_clean_identity(**common, extra_replacements={"甲": "丙"})
    assert one != two, "editing a replacements file must invalidate the cleaned cache"


def test_builtin_replacement_version_follows_the_table():
    """The version is derived from the table, so the two cannot disagree."""
    module = load_module()
    expected = hashlib.sha256(
        json.dumps(module.ZH_REPLACEMENTS, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    assert module.BUILTIN_REPLACEMENTS_VERSION == expected


def test_zh_replacements_come_from_the_sidecar_file():
    """One source of truth: the JSON file, with the embedded table as fallback."""
    module = load_module()
    sidecar = json.loads(
        (Path(__file__).resolve().parents[1] / "zh_replacements.json").read_text(encoding="utf-8")
    )
    expected = {k: v for k, v in sidecar.items() if not k.startswith("_")}
    assert module.ZH_REPLACEMENTS == expected


# ---------------------------------------------------------------------------
# Decoding: `accurate` must decode differently, not merely cache differently.
# ---------------------------------------------------------------------------

def test_accurate_mode_requests_beam_search_from_mlx(monkeypatch, tmp_path):
    module = load_module()
    captured = {}

    class FakeMLX:
        @staticmethod
        def transcribe(path, **kwargs):
            captured.update(kwargs)
            return {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}], "language": "en"}

    monkeypatch.setitem(sys.modules, "mlx_whisper", FakeMLX)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"\x00")
    config = module.resolve_mode_config("accurate", "mlx", None)
    module.transcribe_audio_mlx(config, wav, "en")
    assert captured.get("beam_size") == 5, (
        "accurate promised a higher beam size; it must reach mlx_whisper.transcribe"
    )


def test_balanced_mode_does_not_request_beam_search(monkeypatch, tmp_path):
    module = load_module()
    captured = {}

    class FakeMLX:
        @staticmethod
        def transcribe(path, **kwargs):
            captured.update(kwargs)
            return {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}], "language": "en"}

    monkeypatch.setitem(sys.modules, "mlx_whisper", FakeMLX)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"\x00")
    config = module.resolve_mode_config("balanced", "mlx", None)
    module.transcribe_audio_mlx(config, wav, "en")
    assert "beam_size" not in captured


# ---------------------------------------------------------------------------
# LLM output validation: a wrong "correction" is worse than a surviving typo.
# ---------------------------------------------------------------------------

def _long_source(lines=8):
    return "\n".join(f"这是第{i}行内容，长度足够触发结构检查。" for i in range(1, lines + 1))


def test_faithful_proofread_is_accepted():
    module = load_module()
    source = _long_source()
    accepted, reason = module._validate_llm_output(source, source.replace("内容", "內容"))
    assert accepted, reason


@pytest.mark.parametrize("label,corrupt", [
    ("meta commentary", lambda s: "以下是校对后的文本：\n" + s[: len(s) - 9]),
    ("collapsed structure", lambda s: s.replace("\n", "")),
    ("decode loop", lambda s: "\n".join(["重复的一整行内容在这里出现。"] * 8)),
    ("invented number", lambda s: s.replace("第1行", "第1行 2026 年")),
    ("truncated", lambda s: s[:20]),
    ("empty", lambda s: ""),
])
def test_validation_rejects_each_failure_mode(label, corrupt):
    module = load_module()
    source = _long_source()
    accepted, reason = module._validate_llm_output(source, corrupt(source))
    assert not accepted, f"{label} should have been rejected"
    assert reason, "a rejection must say why"


def test_validation_reasons_are_distinct():
    """Each failure mode must be attributable, not collapsed into one message."""
    module = load_module()
    source = _long_source()
    reasons = {
        module._validate_llm_output(source, corrupt(source))[1]
        for corrupt in (
            lambda s: "",
            lambda s: s[:20],
            lambda s: "\n".join(["重复的一整行内容在这里出现。"] * 8),
            lambda s: s.replace("第1行", "第1行 2026 年"),
        )
    }
    assert len(reasons) == 4, f"reasons collapsed: {reasons}"


# ---------------------------------------------------------------------------
# Proper-noun unification is a heuristic; its guards must hold.
# ---------------------------------------------------------------------------

def test_unification_skips_a_variant_nested_in_a_longer_frequent_span():
    module = load_module()
    text = ("张伟明出席会议。\n" * 9) + "张伟明说。\n"
    unified, applied = module.unify_proper_nouns(text)
    assert unified == text
    assert applied == []


def test_unification_leaves_text_untouched_without_enough_evidence():
    module = load_module()
    text = "甲乙丙出现。\n乙丙丁出现。\n"
    unified, applied = module.unify_proper_nouns(text)
    assert unified == text and applied == []


def test_clean_transcript_can_disable_unification():
    module = load_module()
    text = "".join(f"哈里斯{w}。\n" for w in "一二三四五六七八九十甲") + "哈理斯也出现。\n"
    _, kept = module.clean_transcript(
        text, "zh", llm_backend="none", unify_names=False,
    )
    assert "哈理斯" in kept


# ---------------------------------------------------------------------------
# Safety of the opt-in unification pass, and the failure modes that used to be
# silent: a missing claude CLI, a corrupt cache, a truncated WAV.
# ---------------------------------------------------------------------------

def test_unification_is_off_by_default():
    """`苹果醋` and `苹果汁` differ by one character and are different drinks.

    The heuristic cannot tell that apart from an ASR variant, so the pass must
    not run unless explicitly requested.
    """
    module = load_module()
    text = "苹果汁很受欢迎。\n" * 11 + "苹果醋也很受欢迎。\n"
    _, default_out = module.clean_transcript(text, "zh", llm_backend="none")
    assert "苹果醋" in default_out, "unification must not run by default"


def test_unification_still_works_when_requested():
    module = load_module()
    text = "苹果汁很受欢迎。\n" * 11 + "苹果醋也很受欢迎。\n"
    _, opted_in = module.clean_transcript(
        text, "zh", llm_backend="none", unify_names=True
    )
    assert "苹果醋" not in opted_in


def test_cli_exposes_unify_names_as_opt_in():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "local_transcript.py"), "--help"],
        capture_output=True, text=True,
    )
    assert "--unify-names" in result.stdout
    assert "--no-unify-names" not in result.stdout, "the flag must default to off"


def test_missing_claude_cli_fails_instead_of_returning_unproofread_text(monkeypatch):
    """Returning the original text looked like a successful proofread and got
    cached under the claude identity, so installing the CLI later hit it."""
    module = load_module()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit):
        module.llm_proofread_full("一段足够长的中文文本用于触发分块处理。" * 20, backend="claude")


def test_corrupt_cache_is_treated_as_a_miss(tmp_path):
    module = load_module()
    broken = tmp_path / "clean.json"
    broken.write_text("{ this is not json", encoding="utf-8")
    assert module.load_clean_transcript_cache(broken) is None
    assert not broken.exists(), "a corrupt cache file should be removed, not re-read"


def test_raw_cache_survives_a_write_and_reads_back(tmp_path):
    module = load_module()
    path = tmp_path / "raw.json"
    transcript = module.RawTranscript(language="zh", raw_text="你好", segments=[])
    module.save_raw_transcript_cache(path, transcript)
    assert path.exists()
    assert not list(tmp_path.glob(".*tmp")), "the temp file must not survive the write"
    loaded = module.load_raw_transcript_cache(path)
    assert loaded is not None and loaded.raw_text == "你好"


def test_truncated_wav_is_not_accepted_as_cached_audio(tmp_path):
    module = load_module()
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"\x00" * 200)          # non-empty but not a WAV
    assert not module._is_complete_wav(wav)
    wav.write_bytes(b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"\x00" * 40)
    assert module._is_complete_wav(wav)


def test_dependency_markers_scope_mlx_to_apple_silicon():
    source = (Path(__file__).resolve().parents[1] / "local_transcript.py").read_text(encoding="utf-8")
    header = source[: source.index("# ///", source.index("# /// script") + 5)]
    for line in header.splitlines():
        if "mlx-" in line:
            assert "platform_machine == 'arm64'" in line, (
                f"MLX must not be resolved on non-Apple-Silicon: {line.strip()}"
            )
    assert "faster-whisper" in header, "the CPU fallback must install everywhere"


# ---------------------------------------------------------------------------
# The quality-eval metrics themselves. A CER function nobody checked cannot be
# trusted to grade a corpus later.
# ---------------------------------------------------------------------------

def load_quality_eval():
    path = Path(__file__).resolve().parents[1] / "run_quality_eval.py"
    spec = importlib.util.spec_from_file_location("run_quality_eval", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cer_is_zero_for_an_exact_match():
    qe = load_quality_eval()
    assert qe.character_error_rate("今天天气很好", "今天天气很好") == 0.0


def test_cer_ignores_punctuation_and_spacing():
    qe = load_quality_eval()
    assert qe.character_error_rate("今天天气很好", "今天，天气 很好。") == 0.0


def test_cer_counts_substitutions_insertions_and_deletions():
    qe = load_quality_eval()
    assert qe.character_error_rate("今天天气很好", "今天天气很差") == pytest.approx(1 / 6)
    assert qe.character_error_rate("今天天气很好", "今天天气很") == pytest.approx(1 / 6)
    assert qe.character_error_rate("今天天气很好", "今天天气真的很好") == pytest.approx(2 / 6)


def test_proper_noun_recall_counts_exact_terms():
    qe = load_quality_eval()
    assert qe.proper_noun_recall(["哈里斯", "欧盟"], "哈里斯谈到欧盟。") == (2, 2)
    assert qe.proper_noun_recall(["哈里斯", "欧盟"], "哈理斯谈到欧盟。") == (1, 2)


def test_quality_eval_without_a_corpus_is_a_setup_failure_not_a_result(tmp_path):
    qe = load_quality_eval()
    code = qe.main(["run_quality_eval.py", "--corpus", str(tmp_path)])
    assert code == 2, "a missing corpus must never be reported as passing quality"

# ---------------------------------------------------------------------------
# Orchestration. The previous version of this file tested only the leaf metrics
# and the missing-corpus exit, so the path that actually runs was never executed
# once — and it passed `--formats`, which the transcriber rejects outright.
# `stub_transcriber.py` exercises argv construction, aggregation, regression
# detection and the summary without needing real audio.
# ---------------------------------------------------------------------------

STUB = Path(__file__).resolve().parent / "stub_transcriber.py"


def _make_corpus(tmp_path, canned, reference="今天天气很好哈里斯出席会议", nouns=None):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "a.m4a").write_bytes(b"\x00" * 16)
    (corpus / "a.stub.json").write_text(json.dumps(canned, ensure_ascii=False), encoding="utf-8")
    (corpus / "a.txt").write_text(reference, encoding="utf-8")
    (corpus / "manifest.json").write_text(json.dumps([{
        "audio": "a.m4a", "reference": "a.txt",
        "proper_nouns": nouns if nouns is not None else ["\u54c8\u91cc\u65af"],
        "language": "zh",
    }], ensure_ascii=False), encoding="utf-8")
    return corpus


def test_evaluator_builds_a_command_the_transcriber_accepts():
    """Regression: the evaluator passed `--formats`, which argparse rejects.

    Assert against the transcriber's real parser rather than a remembered flag
    name, so a rename on either side fails here.
    """
    qe = load_quality_eval()
    transcriber = Path(__file__).resolve().parents[1] / "local_transcript.py"
    cmd = qe.build_transcribe_command(
        transcriber, Path("/tmp/a.m4a"), "balanced", Path("/tmp/out.txt"), [], use_uv=False
    )
    assert "--format" in cmd and "--formats" not in cmd

    help_text = subprocess.run(
        [sys.executable, str(transcriber), "--help"], capture_output=True, text=True
    ).stdout
    for flag in [token for token in cmd if token.startswith("--")]:
        assert flag in help_text, f"evaluator passes {flag}, which the transcriber does not accept"


def test_evaluator_prefers_uv_so_pep723_dependencies_are_honoured():
    qe = load_quality_eval()
    cmd = qe.build_transcribe_command(
        Path("/x/t.py"), Path("/tmp/a.m4a"), "fast", Path("/tmp/o.txt"), [], use_uv=True
    )
    assert cmd[:2] == ["uv", "run"], "a bare interpreter ignores the PEP 723 header"


def test_end_to_end_orchestration_against_a_stub_transcriber(tmp_path, capsys):
    qe = load_quality_eval()
    corpus = _make_corpus(tmp_path, {
        "balanced:raw": "今天天气很好哈里斯出席会议",
        "balanced:clean": "今天天气很好哈里斯出席会议",
    })
    code = qe.main([
        "run_quality_eval.py", "--corpus", str(corpus), "--modes", "balanced",
        "--transcriber", str(STUB), "--no-uv",
    ])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "1/1 scenario-modes within thresholds" in out


def test_proper_noun_regression_is_reported_and_fails(tmp_path, capsys):
    """The docs promised that a proofreader corrupting names would surface."""
    qe = load_quality_eval()
    corpus = _make_corpus(tmp_path, {
        "balanced:raw": "今天天气很好哈里斯出席会议",
        "balanced:clean": "今天天气很好哈理斯出席会议",
    })
    code = qe.main([
        "run_quality_eval.py", "--corpus", str(corpus), "--modes", "balanced",
        "--transcriber", str(STUB), "--no-uv",
    ])
    out = capsys.readouterr().out
    assert code == 1
    assert "lost proper nouns" in out


def test_aggregation_covers_every_sample_not_just_the_last():
    """A dict comprehension keyed on mode kept only the final row."""
    qe = load_quality_eval()
    rows = [
        {"mode": "balanced", "dist_baseline": 10, "dist_clean": 10, "ref_len": 1000},
        {"mode": "balanced", "dist_baseline": 0, "dist_clean": 0, "ref_len": 10},
    ]
    totals = qe.aggregate_by_mode(rows)
    assert totals["balanced"]["samples"] == 2
    # Length-weighted: 10 errors over 1010 reference characters — not the 0.0 of
    # the last row, and not the 0.005 a naive per-file average would give.
    assert totals["balanced"]["cer_cleaned"] == pytest.approx(10 / 1010)


def test_failure_count_is_per_scenario_not_per_rule(capsys):
    """Two breaches in one row used to subtract two from the pass count."""
    qe = load_quality_eval()
    row = {
        "audio": "a.m4a", "mode": "balanced",
        "cer_baseline": 0.10, "cer_cleaned": 0.40, "ref_len": 100,
        "dist_baseline": 10, "dist_clean": 40,
        "nouns_found": 0, "nouns_found_baseline": 1, "nouns_total": 1,
    }
    verdicts = qe.judge([row], max_cer=0.15)
    assert len(verdicts) == 1
    assert len(verdicts[0][1]) == 3, "all three reasons should be reported"
    failed = qe.report(verdicts, qe.aggregate_by_mode([row]))
    capsys.readouterr()
    assert failed == 1, "one bad scenario is one failure, however many rules it breaks"


def test_missing_audio_in_manifest_is_a_setup_failure(tmp_path):
    qe = load_quality_eval()
    corpus = _make_corpus(tmp_path, {"balanced:raw": "x", "balanced:clean": "x"})
    (corpus / "a.m4a").unlink()
    code = qe.main([
        "run_quality_eval.py", "--corpus", str(corpus), "--modes", "balanced",
        "--transcriber", str(STUB), "--no-uv",
    ])
    assert code == 2, "a broken corpus is a setup failure, not a quality verdict"


# ---------------------------------------------------------------------------
# Corpus generator. `say -v '?'` lists voices that are only *available for
# download*; an uninstalled one emits ~0.01 s of audio rather than failing, so a
# generator that trusted the exit code would build a corpus of silence and the
# evaluator would score noise.
# ---------------------------------------------------------------------------

def load_corpus_builder():
    path = Path(__file__).resolve().parents[1] / "make_reference_corpus.py"
    spec = importlib.util.spec_from_file_location("make_reference_corpus", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_silent_clip_is_rejected(tmp_path, monkeypatch):
    mc = load_corpus_builder()
    clip = tmp_path / "a.aiff"
    clip.write_bytes(b"\x00" * 4608)          # what an uninstalled voice produces
    monkeypatch.setattr(mc, "clip_duration", lambda path: 0.0116)
    with pytest.raises(RuntimeError) as excinfo:
        mc.check_clip(clip, "哈里斯在会议上强调欧盟的贸易政策", "Eddy")
    assert "not installed" in str(excinfo.value)
    assert "Tingting" in str(excinfo.value), "the error must name a voice that works"


def test_plausible_clip_is_accepted(tmp_path, monkeypatch):
    mc = load_corpus_builder()
    clip = tmp_path / "a.aiff"
    clip.write_bytes(b"\x00" * 300_000)
    monkeypatch.setattr(mc, "clip_duration", lambda path: 5.0)
    mc.check_clip(clip, "哈里斯在会议上强调欧盟的贸易政策", "Tingting")


def test_size_fallback_when_afinfo_is_unavailable(tmp_path, monkeypatch):
    mc = load_corpus_builder()
    monkeypatch.setattr(mc, "clip_duration", lambda path: None)
    clip = tmp_path / "a.aiff"
    clip.write_bytes(b"\x00" * 4608)
    with pytest.raises(RuntimeError):
        mc.check_clip(clip, "哈里斯在会议上强调欧盟的贸易政策", "Eddy")
    clip.write_bytes(b"\x00" * 300_000)
    mc.check_clip(clip, "哈里斯在会议上强调欧盟的贸易政策", "Tingting")


def test_default_voice_is_one_that_actually_synthesises():
    """Eddy is listed on a stock macOS but ships undownloaded."""
    mc = load_corpus_builder()
    source = (Path(__file__).resolve().parents[1] / "make_reference_corpus.py").read_text(
        encoding="utf-8"
    )
    assert '"--voice", default="Tingting"' in source


def test_default_script_covers_the_cases_worth_scoring():
    mc = load_corpus_builder()
    texts = " ".join(entry["text"] for entry in mc.DEFAULT_SCRIPT)
    assert any(entry["proper_nouns"] for entry in mc.DEFAULT_SCRIPT), "no proper nouns to score"
    assert "Kubernetes" in texts, "mixed CJK/Latin term missing"
    assert "噤若寒蝉" in texts, "homophone trap missing"
    ids = [entry["id"] for entry in mc.DEFAULT_SCRIPT]
    assert len(ids) == len(set(ids)), "sample ids must be unique — they become filenames"


def test_manifest_language_reaches_the_transcriber():
    """The field was documented but never forwarded, so it pinned nothing."""
    qe = load_quality_eval()
    cmd = qe.build_transcribe_command(
        Path("/x/t.py"), Path("/tmp/a.m4a"), "balanced", Path("/tmp/o.txt"), [],
        use_uv=False, language="zh",
    )
    assert "--language" in cmd and cmd[cmd.index("--language") + 1] == "zh"


def test_transcriber_passthrough_reaches_the_command():
    qe = load_quality_eval()
    cmd = qe.build_transcribe_command(
        Path("/x/t.py"), Path("/tmp/a.m4a"), "balanced", Path("/tmp/o.txt"), [],
        use_uv=False, passthrough=["--backend", "faster-whisper"],
    )
    assert cmd[cmd.index("--backend") + 1] == "faster-whisper"


# ---------------------------------------------------------------------------
# Gaps the previous round shipped without direct coverage.
# ---------------------------------------------------------------------------

def test_fingerprint_changes_when_content_changes_at_identical_size_and_second(tmp_path):
    """Path + size + whole-second mtime collided on a same-second replacement.

    Forcing the coarse metadata to be identical isolates the content sampling:
    if the fingerprint still matched, a swapped file would reuse the old cache.
    """
    module = load_module()
    media = tmp_path / "clip.bin"
    media.write_bytes(b"A" * 200_000)
    first = module.resolve_media_fingerprint(media)
    stat = media.stat()

    media.write_bytes(b"B" * 200_000)          # same size, different content
    os.utime(media, ns=(stat.st_atime_ns, stat.st_mtime_ns))   # same mtime, to the ns
    assert media.stat().st_size == 200_000
    assert media.stat().st_mtime_ns == stat.st_mtime_ns

    assert module.resolve_media_fingerprint(media) != first, (
        "identical metadata must not be enough to reuse a cache entry"
    )


def test_fingerprint_is_stable_for_an_unchanged_file(tmp_path):
    module = load_module()
    media = tmp_path / "clip.bin"
    media.write_bytes(b"A" * 200_000)
    assert module.resolve_media_fingerprint(media) == module.resolve_media_fingerprint(media)


def test_cache_and_model_roots_are_overridable(monkeypatch, tmp_path):
    """A hardcoded /tmp path leaves no recourse where /tmp is not writable.

    Both roots matter: overriding only the cache still leaves model downloads
    pointing at the unwritable location, which fails just as hard.
    """
    monkeypatch.setenv("LOCAL_TRANSCRIPT_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("LOCAL_TRANSCRIPT_MODELS", str(tmp_path / "models"))
    module = load_module()
    assert str(module.CACHE_ROOT).startswith(str(tmp_path))
    assert str(module.MODEL_DOWNLOAD_ROOT).startswith(str(tmp_path))


def test_no_unoverridable_absolute_paths_remain():
    source = (Path(__file__).resolve().parents[1] / "local_transcript.py").read_text(
        encoding="utf-8"
    )
    for line in source.splitlines():
        if "/tmp/local-transcript" in line and "os.environ.get" not in line:
            assert line.lstrip().startswith("#"), (
                f"hardcoded path with no override: {line.strip()}"
            )


def test_emit_raw_asr_writes_uncleaned_text(tmp_path, monkeypatch):
    """The raw export must bypass OpenCC, replacements and re-segmentation.

    Driven through main() rather than the writer, because the promise is about
    the flag as a user reaches it.
    """
    # CACHE_ROOT is read at import time, so the env var must be set BEFORE the
    # module is loaded — setting it after leaves the hardcoded /tmp path.
    monkeypatch.setenv("LOCAL_TRANSCRIPT_CACHE", str(tmp_path / "cache"))
    module = load_module()
    raw_text = "这是原始的ASR輸出沒有標點也沒有轉換"
    media = tmp_path / "a.m4a"
    media.write_bytes(b"\x00" * 64)
    raw_out = tmp_path / "raw.txt"
    final_out = tmp_path / "final.txt"

    monkeypatch.setattr(module, "require_command", lambda name: name)
    monkeypatch.setattr(
        module, "ensure_audio_cache",
        lambda ffmpeg, src, dst: (dst, "skipped"),
    )
    monkeypatch.setattr(
        module, "transcribe_audio",
        lambda config, wav, hint: module.RawTranscript(
            language="zh", raw_text=raw_text, segments=[],
        ),
    )
    monkeypatch.setattr(sys, "argv", [
        "local_transcript.py", str(media), "--mode", "fast", "--format", "txt",
        "--output", str(final_out), "--no-llm-proofread",
        "--emit-raw-asr", str(raw_out),
    ])
    module.main()

    assert raw_out.exists(), "--emit-raw-asr wrote nothing"
    assert raw_out.read_text(encoding="utf-8") == raw_text, (
        "the raw export must be byte-identical to the ASR output"
    )
    assert final_out.read_text(encoding="utf-8") != raw_text, (
        "the cleaned output should differ, or the export proves nothing"
    )


def test_true_raw_flag_exists_and_uses_emit_raw_asr():
    """Regression: the docstring promised --true-raw before it existed."""
    qe = load_quality_eval()
    source = (Path(__file__).resolve().parents[1] / "run_quality_eval.py").read_text(
        encoding="utf-8"
    )
    assert '"--true-raw"' in source
    assert "--emit-raw-asr" in source, "the flag must actually request a raw export"

    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "run_quality_eval.py"),
         "--help"], capture_output=True, text=True,
    )
    assert "--true-raw" in result.stdout


def test_documented_transcriber_arg_example_is_accepted_by_argparse(tmp_path):
    """The help advertised a form argparse rejects.

    Assert the parser's behaviour rather than the help text: argparse wraps its
    output, so a string match on the example is brittle and would not prove the
    example works anyway.
    """
    script = Path(__file__).resolve().parents[1] / "run_quality_eval.py"

    def invoke(*extra):
        return subprocess.run(
            [sys.executable, str(script), "--corpus", str(tmp_path), *extra],
            capture_output=True, text=True,
        )

    rejected = invoke("--transcriber-arg", "--model-path")
    assert "expected one argument" in rejected.stderr, (
        "the space form should still be rejected — that is why the help must not show it"
    )

    accepted = invoke("--transcriber-arg=--model-path")
    assert "expected one argument" not in accepted.stderr
    # Exits 2 for the missing corpus, not for an argument error.
    assert accepted.returncode == 2 and "setup:" in accepted.stderr

    help_text = subprocess.run(
        [sys.executable, str(script), "--help"], capture_output=True, text=True
    ).stdout
    # argparse wraps long help and can break mid-token ("--transcriber-\narg="),
    # so compare with all whitespace removed rather than merely collapsed.
    squashed = "".join(help_text.split())
    assert "--transcriber-arg=--model-path" in squashed, (
        "the help must show the form that actually parses"
    )


def test_empty_reference_is_a_setup_failure_not_a_perfect_score(tmp_path):
    """An empty reference used to yield CER 0.0 and exit 0."""
    qe = load_quality_eval()
    corpus = _make_corpus(tmp_path, {"balanced:raw": "有输出", "balanced:clean": "有输出"})
    (corpus / "a.txt").write_text("   \n", encoding="utf-8")
    code = qe.main([
        "run_quality_eval.py", "--corpus", str(corpus), "--modes", "balanced",
        "--transcriber", str(STUB), "--no-uv",
    ])
    assert code == 2, "a corpus that cannot be scored is a setup failure"


def test_introduced_errors_are_counted_even_when_net_cer_is_flat(tmp_path, capsys):
    """Net CER cancels a repair against a new break; the counts must not."""
    qe = load_quality_eval()
    reference = "今天天气很好哈里斯出席会议"
    corpus = _make_corpus(tmp_path, {
        "balanced:raw": "今天天汽很好哈里斯出席会议",     # one error
        "balanced:clean": "今天天气很好哈理斯出席会议",   # fixes it, breaks another
    }, reference=reference)
    fixed, introduced = qe.error_delta(
        reference, "今天天汽很好哈里斯出席会议", "今天天气很好哈理斯出席会议",
    )
    assert (fixed, introduced) == (1, 1)

    code = qe.main([
        "run_quality_eval.py", "--corpus", str(corpus), "--modes", "balanced",
        "--transcriber", str(STUB), "--no-uv",
    ])
    out = capsys.readouterr().out
    assert "introduced 1 character error" in out
    assert code == 1, "an even trade must not pass silently"


# -- Mixed-width punctuation: the ",，" artifact -----------------------------
# join_lines used to treat a line ending in a halfwidth comma as unpunctuated
# and append a full-width one, manufacturing ",，" on every such boundary.
# Observed 185 times in a single 31-minute transcript.

def test_join_lines_does_not_append_a_second_comma_after_a_halfwidth_one():
    module = load_module()
    joined = module.join_lines(
        ["今天要解读的是一本新书,", "叫做AI自动化与战争,", "副标题是军事科技复合体的兴起。"],
        "zh",
    )
    assert not any(",，" in sentence for sentence in joined), joined


def test_normalize_zh_punctuation_repairs_halfwidth_comma_before_any_character():
    module = load_module()
    # Before a full-width comma (the legacy artifact) and before Latin text —
    # neither was reachable by the old both-sides CJK lookaround.
    assert module.normalize_zh_punctuation("战役里,，Palantir开发") == "战役里，Palantir开发"
    assert module.normalize_zh_punctuation("战役里,Palantir开发") == "战役里，Palantir开发"


def test_clean_transcript_leaves_no_mixed_width_comma(monkeypatch):
    module = load_module()
    raw = "\n".join(["今天要解读的是一本新书,", "叫做AI自动化与战争,", "副标题是军事科技复合体的兴起。"])
    language, final_text = module.clean_transcript(raw, raw_language_hint="zh")
    assert language == "zh"
    assert ",，" not in final_text
    assert "," not in final_text


# -- Paragraph breaks must not invent sentence boundaries -------------------
# paragraphize used to cut at a character count and stamp "。" on the stump,
# splitting single sentences in two ("把青霉素从一个科学项目。变成了...").

def test_paragraphize_waits_for_the_sentence_to_end():
    module = load_module()
    clause = "复杂性投资的边际收益递减是本书的核心论点" * 14  # past the 260-char soft limit
    tail = "而这条曲线最终会转负。"
    paragraphs = [p for p in module.paragraphize([clause, tail], "zh").strip().split("\n\n") if p]
    assert len(paragraphs) == 1, [p[:40] for p in paragraphs]
    assert paragraphs[0] == clause + tail


def test_paragraphize_bounds_overflow_without_stamping_a_period():
    module = load_module()
    clause = "没有句读一直讲下去的内容片段" * 15
    paragraphs = [p for p in module.paragraphize([clause] * 5, "zh").strip().split("\n\n") if p]
    assert len(paragraphs) >= 2, "an unterminated stream must still be bounded"
    # An interior break is a layout decision, not a claim about the speech.
    assert not paragraphs[0].endswith("。")
    # The document does end, so its last paragraph may be terminated.
    assert paragraphs[-1].endswith("。")


def test_paragraphize_keeps_breaking_on_real_sentence_ends():
    module = load_module()
    sentence = "这是一段说完就收尾的完整句子内容。" * 20
    paragraphs = [p for p in module.paragraphize([sentence] * 3, "zh").strip().split("\n\n") if p]
    assert len(paragraphs) == 3


# -- A leaked prompt label is a failed proofread ----------------------------
# The model once copied "待校对文本:" into the middle of the answer; the
# head-only prefix test could not see it.

def test_validate_llm_output_rejects_a_leaked_prompt_label():
    module = load_module()
    accepted, reason = module._validate_llm_output(
        "横轴是一个社会往复杂性里投入进去的东西包括人力粮食税收官员的脑力",
        "横轴是一个社会往复杂性里投入进去的东西，待校对文本:，包括人力粮食税收官员的脑力",
    )
    assert accepted is False
    assert "待校对文本" in reason


def test_validate_llm_output_allows_a_label_the_source_already_contained():
    module = load_module()
    source = "我们把待校对文本这个说法解释一下再往下讲后面的内容"
    accepted, reason = module._validate_llm_output(source, source + "。")
    assert accepted is True, reason


# -- LLM proofreading is opt-in --------------------------------------------

def test_llm_proofreading_is_opt_in_on_the_command_line(monkeypatch):
    module = load_module()
    monkeypatch.setattr(sys, "argv", ["local_transcript.py", "clip.mp4"])
    assert module.parse_args().llm_backend == "none"


def test_clean_transcript_does_not_proofread_unless_asked(monkeypatch):
    module = load_module()
    called = []
    monkeypatch.setattr(
        module, "llm_proofread_full",
        lambda *a, **k: called.append(True) or "",
    )
    module.clean_transcript("今天要解读的是一本新书。", raw_language_hint="zh")
    assert called == []


# -- SKILL.md must not drift from the code ---------------------------------

def _skill_md() -> str:
    return (Path(__file__).resolve().parents[2] / "SKILL.md").read_text(encoding="utf-8")


def test_skill_md_does_not_claim_proofreading_is_on_by_default():
    text = _skill_md()
    # Scoped to the emitted claim, not to prose that explains the change.
    assert "LLM proofreading: enabled by default" not in text
    assert "LLM proofreading: **off by default**" in text


def test_skill_md_documents_the_opt_in_rationale():
    assert "## LLM Proofreading Is Opt-In" in _skill_md()


def test_skill_md_default_matches_the_parser_default(monkeypatch):
    module = load_module()
    monkeypatch.setattr(sys, "argv", ["local_transcript.py", "clip.mp4"])
    assert module.parse_args().llm_backend == "none"
    assert "`--llm-backend` defaults to `none`" in _skill_md()


def test_paragraph_overflow_stays_close_to_the_soft_limit():
    """Whisper zh emits almost no sentence terminators, so the wait must be short.

    With an unbounded wait every paragraph runs to the hard cap; the point of
    the cap is that a transcript with no periods still reads like prose.
    """
    module = load_module()
    assert module.PARAGRAPH_HARD_RATIO <= 1.5
    clause = "一段没有句号的转写内容" * 12  # 132 chars, never terminates
    paragraphs = [
        p for p in module.paragraphize([clause] * 12, "zh").strip().split("\n\n") if p
    ]
    longest = max(len(p) for p in paragraphs)
    assert longest <= 260 * module.PARAGRAPH_HARD_RATIO + len(clause)
    assert len(paragraphs) >= 4, "an unpunctuated transcript must still be paragraphed"


def test_llm_backend_help_does_not_advertise_local_as_the_default(capsys, monkeypatch):
    """The help string is the second place a default is claimed. Keep it honest."""
    module = load_module()
    monkeypatch.setattr(sys, "argv", ["local_transcript.py", "--help"])
    with pytest.raises(SystemExit):
        module.parse_args()
    help_text = capsys.readouterr().out
    # "--llm-backend" also appears in the usage line and inside the
    # --no-llm-proofread description, so anchor on the option-list entry: a
    # line that starts at indent 2 and runs until the next option.
    match = re.search(
        r"^  --llm-backend .*?(?=^  --)", help_text, re.MULTILINE | re.DOTALL
    )
    assert match, help_text
    section = match.group(0)
    assert "Defaults to 'none'" in section, section
    assert "(default)" not in section, "a stale default is advertised in --help"
