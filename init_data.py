from __future__ import annotations

import argparse
import time
from pathlib import Path

from data_pipeline.milvus_loader import MILVUS_DB_PATH, load_rules_from_xls
from data_pipeline.sqlite_loader import DB_PATH, load_from_xls
from data_pipeline.xls_parser import XLSPipeline

ROOT = Path(__file__).resolve().parent
DEFAULT_XLS = ROOT / "20260713.xls"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="重建 XLS 费率与规则数据")
    parser.add_argument("--xls", type=Path, default=DEFAULT_XLS, help="XLS 文件路径")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--milvus", type=Path, default=MILVUS_DB_PATH, help="Milvus Lite 数据库路径")
    parser.add_argument("--dry-run", action="store_true", help="只解析统计，不写入数据库")
    parser.add_argument("--verbose", action="store_true", help="输出详细处理日志")
    return parser.parse_args(argv)


def _validate_xls(xls_path: Path) -> None:
    if not xls_path.is_file():
        raise FileNotFoundError(f"文件不存在: {xls_path}")
    if xls_path.suffix.lower() != ".xls":
        raise ValueError(f"文件格式错误，仅支持 .xls: {xls_path}")


def _parse_preview(xls_path: Path, verbose: bool) -> tuple[int, int]:
    pipeline = XLSPipeline(xls_path)
    rates = pipeline.parse_all()
    rules = pipeline.extract_all_rules()
    if verbose:
        print(f"解析工作表: {len(pipeline.sheet_names)} 个")
        print(f"费率记录: {len(rates)} 条")
        print(f"规则文本: {len(rules)} 条")
    return len(rates), len(rules)


def run(
    xls_path: str | Path = DEFAULT_XLS,
    db_path: str | Path = DB_PATH,
    milvus_path: str | Path = MILVUS_DB_PATH,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    started = time.perf_counter()
    xls = Path(xls_path)
    try:
        _validate_xls(xls)
        if dry_run:
            rate_count, rule_count = _parse_preview(xls, verbose)
            print("dry-run：未写入 SQLite / Milvus")
        else:
            if verbose:
                print(f"开始导入: {xls}")
            rate_count = load_from_xls(xls, db_path)
            if verbose:
                print(f"SQLite 导入完成: {rate_count} 条")
            rule_count = load_rules_from_xls(xls, milvus_path)
            if verbose:
                print(f"Milvus 导入完成: {rule_count} 条")

        elapsed = time.perf_counter() - started
        print(f"已导入 {rate_count} 个渠道费率")
        print(f"已导入 {rule_count} 条规则")
        print(f"总耗时: {elapsed:.2f} 秒")
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 2
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"导入失败: {exc}", file=__import__("sys").stderr)
        return 1
    except Exception as exc:
        print(f"导入失败: {type(exc).__name__}: {exc}", file=__import__("sys").stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args.xls, args.db, args.milvus, args.dry_run, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
