import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_redaction_boundary.py"
SPEC = spec_from_file_location("check_redaction_boundary", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_pattern_fingerprints_do_not_expose_private_entries(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text("private-fixed-entry\nre:private-[0-9]+\n", encoding="utf-8")

    patterns = MODULE._load_patterns(denylist)

    assert len(patterns) == 2
    assert all(len(pattern.fingerprint) == 12 for pattern in patterns)
    assert all("private" not in pattern.fingerprint for pattern in patterns)


def test_fixed_entries_are_scanned_in_binary_files(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text("binary-marker\n", encoding="utf-8")
    binary = tmp_path / "asset.bin"
    binary.write_bytes(b"\x89PNG\r\n\x1a\n\xffBINARY-MARKER\x00")

    hits = MODULE._scan([str(binary)], MODULE._load_patterns(denylist))

    assert len(hits) == 1
    assert hits[0][0] == str(binary)


def test_regex_entries_scan_printable_binary_content(tmp_path: Path) -> None:
    denylist = tmp_path / "denylist.txt"
    denylist.write_text(r"re:account-[0-9]{4}" + "\n", encoding="utf-8")
    binary = tmp_path / "archive.bin"
    binary.write_bytes(b"\xff\xfeheader\x00account-1234\x80tail")

    hits = MODULE._scan([str(binary)], MODULE._load_patterns(denylist))

    assert len(hits) == 1
    assert hits[0][0] == str(binary)
