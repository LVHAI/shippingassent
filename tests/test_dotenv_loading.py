from __future__ import annotations


def test_init_data_loads_project_dotenv(monkeypatch):
    import init_data

    calls = []
    monkeypatch.setattr(init_data, "load_dotenv", lambda *args, **kwargs: calls.append((args, kwargs)) or True)

    assert init_data.load_environment() is True
    assert calls == [((init_data.ROOT / ".env",), {})]
