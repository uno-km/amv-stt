# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
from unittest.mock import patch

from termux_stt.cli.main import _run_cli


def test_doctor_command_runs(capsys):
    with patch("sys.argv", ["termux-stt", "doctor"]):
        _run_cli()
    captured = capsys.readouterr()
    assert "System Environment Check:" in captured.out
    assert "Doctor check complete." in captured.out


def test_models_list_command(capsys):
    with patch("sys.argv", ["termux-stt", "models", "list"]):
        _run_cli()
    captured = capsys.readouterr()
    assert "Cached Local Models" in captured.out
    assert "Available Registry Models" in captured.out
    assert "whisper" in captured.out


def test_install_command():
    from unittest.mock import patch
    from termux_stt.cli.main import main

    with patch("sys.argv", ["termux-stt", "install"]), patch("termux_stt.platform.installer.EngineInstaller.install_standard") as mock_inst:
        mock_inst.return_value = {"whisper": True, "model(tiny)": True}
        main()
        mock_inst.assert_called_once()


def test_install_command_all():
    from unittest.mock import patch
    from termux_stt.cli.main import main

    with patch("sys.argv", ["termux-stt", "install", "--all"]), patch("termux_stt.platform.installer.EngineInstaller.install_all") as mock_inst:
        mock_inst.return_value = {"whisper": True, "sherpa": True, "diarization": True, "model(tiny)": True}
        main()
        mock_inst.assert_called_once()


def test_benchmark_duration_from_wave_header(capsys):
    import os
    import struct
    import tempfile
    import wave
    from unittest.mock import MagicMock

    from termux_stt.cli.benchmark import run_benchmark

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        frames = int(3.5 * 16000)
        wf.writeframes(struct.pack("<" + "h" * frames, *([0] * frames)))

    try:
        args = MagicMock()
        args.audio = tmp.name
        args.engine = "whisper"
        args.model = "tiny"
        args.lang = "ko"
        args.threads = 1
        args.vad = False

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "테스트 텍스트"
        mock_result.segments = [MagicMock()]
        mock_engine.transcribe.return_value = mock_result

        with patch("termux_stt.cli.benchmark.create_engine", return_value=mock_engine):
            with patch("termux_stt.cli.benchmark.get_audio_info", side_effect=RuntimeError("ffprobe missing")):
                run_benchmark(args)

        captured = capsys.readouterr().out
        assert "Audio Duration: 3.50s" in captured
        assert "Real Time Factor (RTF):" in captured
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)


def test_benchmark_duration_unknown_no_fake_10s(capsys):
    import os
    import tempfile
    from unittest.mock import MagicMock

    from termux_stt.cli.benchmark import run_benchmark

    tmp = tempfile.NamedTemporaryFile(suffix=".raw", delete=False)
    tmp.write(b"not a valid wav or media file")
    tmp.close()

    try:
        args = MagicMock()
        args.audio = tmp.name
        args.engine = "whisper"
        args.model = "tiny"
        args.lang = "ko"
        args.threads = 1
        args.vad = False

        mock_engine = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "테스트"
        mock_result.segments = []
        mock_engine.transcribe.return_value = mock_result

        with patch("termux_stt.cli.benchmark.create_engine", return_value=mock_engine):
            with patch("termux_stt.cli.benchmark.get_audio_info", side_effect=RuntimeError("ffprobe missing")):
                run_benchmark(args)

        captured = capsys.readouterr().out
        assert "Audio Duration: Unknown" in captured
        assert "Real Time Factor (RTF): N/A" in captured
        assert "Audio Duration: 10.00s" not in captured
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)

