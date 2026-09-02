from __future__ import annotations

import argparse
from pathlib import Path


def test_parse_args_supports_xls_flag_and_dry_run(monkeypatch):
    import init_data

    monkeypatch.setattr("sys.argv", ["init_data.py", "--xls", "custom.xls", "--dry-run", "--verbose"])
    args = init_data.parse_args()

    assert args.xls == Path("custom.xls")
    assert args.dry_run is True
    assert args.verbose is True


def test_parse_args_defaults_to_project_workbook(monkeypatch):
    import init_data

    monkeypatch.setattr("sys.argv", ["init_data.py"])
    args = init_data.parse_args()

    assert args.xls == init_data.DEFAULT_XLS
    assert args.dry_run is False
    assert args.verbose is False


def test_dry_run_parses_without_writing(monkeypatch, tmp_path: Path, capsys):
    import init_data

    xls = tmp_path / "rates.xls"
    xls.write_bytes(b"xls")
    calls = []

    class FakePipeline:
        def __init__(self, path):
            calls.append(("pipeline", Path(path)))

        def parse_all(self):
            calls.append(("parse_all",))
            return [{"channel_name": "UPS"}]

        def extract_all_rules(self):
            calls.append(("extract_all_rules",))
            return [{"content": "申报要求"}]

    monkeypatch.setattr(init_data, "XLSPipeline", FakePipeline)
    monkeypatch.setattr(init_data, "load_from_xls", lambda *args, **kwargs: calls.append(("sqlite",)) or 1)
    monkeypatch.setattr(init_data, "load_rules_from_xls", lambda *args, **kwargs: calls.append(("milvus",)) or 1)

    code = init_data.run(xls, dry_run=True, verbose=False)

    assert code == 0
    assert ("sqlite",) not in calls
    assert ("milvus",) not in calls
    output = capsys.readouterr().out
    assert "dry-run" in output
    assert "1" in output


def test_run_rebuilds_sqlite_and_milvus_and_prints_summary(monkeypatch, tmp_path: Path, capsys):
    import init_data

    xls = tmp_path / "rates.xls"
    xls.write_bytes(b"xls")
    calls = []

    monkeypatch.setattr(init_data, "load_from_xls", lambda path, db: calls.append(("sqlite", Path(path), Path(db))) or 120)
    monkeypatch.setattr(init_data, "load_rules_from_xls", lambda path, milvus: calls.append(("milvus", Path(path), Path(milvus))) or 250)

    code = init_data.run(xls, db_path=tmp_path / "shipping.db", milvus_path=tmp_path / "milvus.db", dry_run=False, verbose=False)

    assert code == 0
    assert calls == [
        ("sqlite", xls, tmp_path / "shipping.db"),
        ("milvus", xls, tmp_path / "milvus.db"),
    ]
    output = capsys.readouterr().out
    assert "已导入 120 个渠道费率" in output
    assert "已导入 250 条规则" in output
    assert "总耗时" in output


def test_run_reports_missing_xls_without_writing(monkeypatch, tmp_path: Path, capsys):
    import init_data

    calls = []
    monkeypatch.setattr(init_data, "load_from_xls", lambda *args, **kwargs: calls.append("sqlite"))
    monkeypatch.setattr(init_data, "load_rules_from_xls", lambda *args, **kwargs: calls.append("milvus"))

    code = init_data.run(tmp_path / "missing.xls", dry_run=False, verbose=False)

    assert code != 0
    assert calls == []
    assert "文件不存在" in capsys.readouterr().err
