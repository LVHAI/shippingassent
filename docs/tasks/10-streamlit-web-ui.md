# 10: Streamlit Web UI

**What to build:** 提供浏览器可用的 Web 界面，支持聊天对话、历史消息展示、XLS 数据导入和渠道浏览。替代 CLI 成为主要交互方式。

**Blocked by:** 09 LangGraph 完整 Agent

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `app.py` 实现 Streamlit 应用，包含3个页面：聊天、数据导入、渠道浏览
- [ ] **聊天页面**：
  - 使用 `st.chat_message` 和 `st.chat_input` 实现对话界面
  - 用户输入后调用 LangGraph Agent，流式或完整展示回复
  - 对话历史持久化在 `st.session_state`，刷新页面不丢失
  - 支持多轮对话和追问
- [ ] **数据导入页面**：
  - 文件上传组件（`st.file_uploader`），接受 .xls 文件
  - 上传后自动执行全量导入（SQLite + Milvus）
  - 展示导入进度和结果摘要（渠道数量、规则数量）
  - 导入失败时展示错误信息
- [ ] **渠道浏览页面**：
  - 侧边栏列出所有已导入渠道（按路向/国家分组）
  - 点击渠道展示详细信息（费率表、规则说明）
  - 支持搜索/筛选
- [ ] `streamlit run app.py` 启动成功，浏览器可访问
- [ ] 端到端测试：在浏览器中完成一次完整对话（查询运费 + 查询规则 + 追问）

## Technical notes

- 参考 ADR-006：Streamlit 选型
- LangGraph Agent 的调用需要适配 Streamlit 的同步模型（可能用 `run_in_executor` 包装异步调用）
- 数据导入页面需要保存上传文件到临时目录，然后调用 `init_data.py` 的逻辑
- 渠道浏览页面直接查询 SQLite，不走 Agent
- 页面路由使用 `st.sidebar.radio` 或 Streamlit 多页面机制
