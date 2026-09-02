from __future__ import annotations

import hashlib
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from agent.graph import run_once
from data_pipeline.milvus_loader import MILVUS_DB_PATH, MilvusRuleLoader, load_rules_from_xls
from data_pipeline.sqlite_loader import DB_PATH, load_from_xls

ROOT = Path(__file__).resolve().parent
PAGE_NAMES = ["聊天", "数据导入", "渠道浏览"]


def load_environment() -> bool:
    return bool(load_dotenv(ROOT / ".env"))


load_environment()


def run_agent(user_input: str, conversation_id: str, previous_state: dict[str, Any] | None = None) -> dict[str, Any]:
    return run_once(user_input, previous_state, conversation_id)


def import_xls_data(xls_path: str | Path, db_path: str | Path, milvus_path: str | Path) -> dict[str, int]:
    rate_count = load_from_xls(xls_path, db_path=db_path)
    rule_count = load_rules_from_xls(xls_path, uri=milvus_path)
    return {"rate_count": rate_count, "rule_count": rule_count}


def import_uploaded_xls(uploaded_path: str | Path, db_path: str | Path = DB_PATH, milvus_path: str | Path = MILVUS_DB_PATH) -> dict[str, int]:
    return import_xls_data(uploaded_path, db_path, milvus_path)


def list_channels(db_path: str | Path = DB_PATH, search: str = "") -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.is_file():
        return []
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM channels ORDER BY region, countries, channel_name")]
    if search:
        term = search.casefold()
        rows = [row for row in rows if term in " ".join(str(row.get(key) or "") for key in ("region", "countries", "channel_name", "cargo_type", "sheet_name")).casefold()]
    return rows


def group_channels(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        region = row.get("region") or "未分类"
        grouped.setdefault(region, []).append(row)
    return grouped


def get_channel_detail(db_path: str | Path, channel_id: int) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    return dict(row) if row else {}


def get_channel_rules(
    milvus_path: str | Path,
    sheet_name: str | None = None,
    channel_name: str | None = None,
    rule_category: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    loader = MilvusRuleLoader(uri=milvus_path)
    return loader.list_rules(sheet_name=sheet_name, channel_name=channel_name, rule_category=rule_category, limit=limit)


def _chat_page() -> None:
    st.title("运费助手")
    conversation_id = st.session_state.setdefault("conversation_id", str(uuid.uuid4()))
    messages = st.session_state.setdefault("messages", [])
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("例如：美国 5kg 普货多少钱？")
    if prompt:
        messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                state = run_agent(prompt, conversation_id)
                response = state.get("response", "")
            except Exception as exc:
                response = f"处理失败：{exc}"
            st.markdown(response)
        messages.append({"role": "assistant", "content": response})


def _import_page() -> None:
    st.title("数据导入")
    uploaded = st.file_uploader("上传 XLS 文件", type=["xls"])
    if uploaded is None:
        return

    payload = uploaded.getvalue()
    upload_key = hashlib.sha256(uploaded.name.encode("utf-8") + payload).hexdigest()
    imported_key = st.session_state.get("last_imported_upload_key")
    if imported_key == upload_key:
        st.success("当前文件已完成全量导入")
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="shippingassent-"))
    temp_file = temp_dir / uploaded.name
    try:
        temp_file.write_bytes(payload)
        with st.spinner("正在导入 SQLite + Milvus…"):
            result = import_uploaded_xls(temp_file)
        st.session_state["last_imported_upload_key"] = upload_key
        st.success("导入完成")
        st.metric("渠道数量", result["rate_count"])
        st.metric("规则数量", result["rule_count"])
    except Exception as exc:
        st.error(f"导入失败：{exc}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _render_channel_sidebar(grouped: dict[str, list[dict[str, Any]]]) -> int:
    st.sidebar.subheader("已导入渠道")
    selected_id: int | None = None
    for region, region_rows in grouped.items():
        with st.sidebar.expander(region, expanded=True):
            labels = [
                f"{row['channel_name']} · {row.get('countries') or '未知国家'} · {row.get('cargo_type') or '未知货物'}"
                for row in region_rows
            ]
            selected_label = st.radio("渠道", labels, key=f"sidebar-channel-{region}", label_visibility="collapsed")
            selected_id = next(row["id"] for row in region_rows if labels[region_rows.index(row)] == selected_label)
    if selected_id is None:
        raise RuntimeError("没有可选择的渠道")
    return selected_id


def _browse_page() -> None:
    st.title("渠道浏览")
    search = st.text_input("搜索渠道 / 国家 / 货物类型")
    rows = list_channels(search=search)
    if not rows:
        st.info("暂无已导入渠道")
        return

    grouped = group_channels(rows)
    selected_id = _render_channel_sidebar(grouped)
    detail = get_channel_detail(DB_PATH, selected_id)
    if not detail:
        st.warning("未找到渠道详情")
        return

    st.subheader(f"{detail.get('channel_name') or '未命名渠道'} · {detail.get('countries') or '未知国家'}")
    st.markdown("### 费率表")
    st.json({
        "渠道": detail.get("channel_name"),
        "国家": detail.get("countries"),
        "货物类型": detail.get("cargo_type"),
        "重量下限": detail.get("weight_min"),
        "重量上限": detail.get("weight_max"),
        "每公斤价格": detail.get("price_per_kg"),
        "处理费": detail.get("handling_fee"),
        "首重": detail.get("first_weight"),
        "首重价格": detail.get("first_weight_price"),
        "续重": detail.get("additional_weight"),
        "续重价格": detail.get("additional_weight_price"),
        "计费规则": detail.get("billing_rules"),
        "时效": detail.get("transit_time"),
        "承运商": detail.get("carrier"),
        "服务类型": detail.get("service_type"),
        "备注": detail.get("notes"),
    })

    st.markdown("### 规则说明")
    try:
        rules = get_channel_rules(MILVUS_DB_PATH, detail.get("sheet_name"), detail.get("channel_name"))
    except Exception as exc:
        st.warning(f"规则加载失败：{exc}")
        rules = []
    if not rules:
        st.info("该渠道暂无规则说明")
    else:
        for rule in rules:
            category = rule.get("rule_category") or "其他"
            st.markdown(f"**{category}**：{rule.get('text') or ''}")


def main() -> None:
    st.set_page_config(page_title="运费助手", page_icon="🚚", layout="wide")
    page = st.sidebar.radio("功能", PAGE_NAMES)
    if page == "聊天":
        _chat_page()
    elif page == "数据导入":
        _import_page()
    else:
        _browse_page()


if __name__ == "__main__":
    main()
