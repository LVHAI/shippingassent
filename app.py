from __future__ import annotations

import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from typing import Any

import streamlit as st

from agent.graph import run_once
from data_pipeline.milvus_loader import MILVUS_DB_PATH, load_rules_from_xls
from data_pipeline.sqlite_loader import DB_PATH, load_from_xls

PAGE_NAMES = ["聊天", "数据导入", "渠道浏览"]


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


def get_channel_detail(db_path: str | Path, channel_id: int) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    return dict(row) if row else {}


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
    if st.button("开始全量导入"):
        temp_dir = Path(tempfile.mkdtemp(prefix="shippingassent-"))
        temp_file = temp_dir / uploaded.name
        try:
            temp_file.write_bytes(uploaded.getvalue())
            with st.spinner("正在导入 SQLite + Milvus…"):
                result = import_uploaded_xls(temp_file)
            st.success("导入完成")
            st.metric("渠道数量", result["rate_count"])
            st.metric("规则数量", result["rule_count"])
        except Exception as exc:
            st.error(f"导入失败：{exc}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _browse_page() -> None:
    st.title("渠道浏览")
    search = st.text_input("搜索渠道 / 国家 / 货物类型")
    rows = list_channels(search=search)
    if not rows:
        st.info("暂无已导入渠道")
        return

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        region = row.get("region") or "未分类"
        grouped.setdefault(region, []).append(row)

    for region, region_rows in grouped.items():
        st.subheader(region)
        options = {f"{row['channel_name']} · {row.get('countries') or '未知国家'} · {row.get('cargo_type') or '未知货物'}": row["id"] for row in region_rows}
        selected = st.selectbox("选择渠道", list(options), key=f"channel-{region}")
        detail = get_channel_detail(DB_PATH, options[selected])
        if detail:
            st.json(detail)


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
