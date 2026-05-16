import importlib

import backend.main as m


def test_cache_evict_removes_memory_and_disk(tmp_path, monkeypatch):
    key = "11111111-1111-1111-1111-111111111111"
    monkeypatch.setattr(m, "_CACHE_DIR", tmp_path)
    m._cleaned_cache[key] = {"df": None, "stats": {}}
    pkl = tmp_path / f"{key}.pkl"
    pkl.write_bytes(b"x")

    removed = m._cache_evict(key)

    assert removed is True
    assert key not in m._cleaned_cache
    assert not pkl.exists()


def test_cache_evict_missing_is_safe():
    assert m._cache_evict("22222222-2222-2222-2222-222222222222") is False
