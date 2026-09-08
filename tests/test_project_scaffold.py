from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def test_python_version_is_supported():
    assert sys.version_info >= (3, 11)

def test_required_directories_exist():
    for name in ("docs", "data", "vectordb", "agent", "data_pipeline"):
        assert (ROOT / name).is_dir(), f"missing required directory: {name}"

def test_required_package_initializers_exist():
    assert (ROOT / "agent" / "__init__.py").is_file()
    assert (ROOT / "data_pipeline" / "__init__.py").is_file()

def test_runtime_directories_have_gitkeep():
    assert (ROOT / "data" / ".gitkeep").is_file()
    assert (ROOT / "vectordb" / ".gitkeep").is_file()

def test_env_example_declares_dashscope_api_key():
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "DASHSCOPE_API_KEY=" in content

def test_gitignore_excludes_runtime_data_and_secrets():
    content = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in content
    assert ".venv" in content
    assert "data/" in content
    assert "vectordb/" in content
    assert "__pycache__/" in content

def test_requirements_contain_runtime_dependencies():
    content = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for dependency in ("langgraph", "dashscope", "pymilvus[milvus-lite]", "pandas", "xlrd", "streamlit"):
        assert dependency in content, f"missing dependency: {dependency}"
