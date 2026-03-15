import importlib.util
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

    unified = module.unify_proper_nouns(text)

    assert "哈理斯" not in unified
    assert unified.count("哈里斯") == 12


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
