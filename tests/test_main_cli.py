from __future__ import annotations

import main


def test_cli_exits_cleanly_after_response(monkeypatch, capsys):
    inputs = iter(["你好", "exit"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(main, "run_once", lambda user_input, state: {"response": "你好！"})

    main.main()

    output = capsys.readouterr().out
    assert "运费助手已启动" in output
    assert "助手：你好！" in output
    assert "再见！" in output
