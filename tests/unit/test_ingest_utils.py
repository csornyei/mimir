import hashlib
from datetime import date, datetime

from agent_core.rag.ingest import _parse_metadata, _sha256


# ---------------------------------------------------------------------------
# _sha256
# ---------------------------------------------------------------------------


def test_sha256_correct_hash(tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"hello world")
    expected = hashlib.sha256(b"hello world").hexdigest()
    assert _sha256(f) == expected


def test_sha256_different_content_gives_different_hash(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_bytes(b"hello")
    f2.write_bytes(b"world")
    assert _sha256(f1) != _sha256(f2)


def test_sha256_same_content_gives_same_hash(tmp_path):
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_bytes(b"same content")
    f2.write_bytes(b"same content")
    assert _sha256(f1) == _sha256(f2)


def test_sha256_is_hex_string(tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"data")
    result = _sha256(f)
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


# ---------------------------------------------------------------------------
# _parse_metadata
# ---------------------------------------------------------------------------


def test_parse_metadata_drops_none():
    result = _parse_metadata({"keep": "value", "drop": None})
    assert "drop" not in result
    assert result["keep"] == "value"


def test_parse_metadata_passes_through_str():
    result = _parse_metadata({"s": "hello"})
    assert result["s"] == "hello"


def test_parse_metadata_passes_through_int():
    result = _parse_metadata({"i": 42})
    assert result["i"] == 42


def test_parse_metadata_passes_through_float():
    result = _parse_metadata({"f": 3.14})
    assert result["f"] == 3.14


def test_parse_metadata_passes_through_bool():
    result = _parse_metadata({"b": True})
    assert result["b"] is True


def test_parse_metadata_converts_date():
    d = date(2024, 6, 15)
    result = _parse_metadata({"d": d})
    assert result["d"] == "2024-06-15"


def test_parse_metadata_converts_datetime():
    dt = datetime(2024, 6, 15, 12, 30, 0)
    result = _parse_metadata({"dt": dt})
    assert result["dt"] == dt.isoformat()


def test_parse_metadata_converts_unknown_type_to_str():
    class Custom:
        def __str__(self):
            return "custom_repr"

    result = _parse_metadata({"c": Custom()})
    assert result["c"] == "custom_repr"


def test_parse_metadata_empty():
    assert _parse_metadata({}) == {}


def test_parse_metadata_all_none_values():
    result = _parse_metadata({"a": None, "b": None})
    assert result == {}
