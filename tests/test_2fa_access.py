from types import SimpleNamespace

from app.core import totp
from app.core.access import pick_group, tags_from_group

RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # ASCII "12345678901234567890"


def test_totp_rfc6238_vectors():
    assert totp.verify(RFC_SECRET, "287082", now=59) is not None
    assert totp.verify(RFC_SECRET, "081804", now=1111111109) is not None
    assert totp.verify(RFC_SECRET, "005924", now=1234567890) is not None
    assert totp.verify(RFC_SECRET, "000000", now=59) is None
    assert totp.verify(RFC_SECRET, "28708", now=59) is None  # wrong length


def test_totp_window_and_replay():
    step = totp.verify(RFC_SECRET, "287082", now=59)
    assert totp.verify(RFC_SECRET, "287082", last_step=step, now=59) is None  # same code twice
    assert totp.verify(RFC_SECRET, "287082", now=59 + 30) is not None  # one step of clock drift
    assert totp.verify(RFC_SECRET, "287082", now=59 + 300) is None


def test_provisioning_uri_and_secret():
    assert len(totp.new_secret()) == 32
    uri = totp.provisioning_uri("ABC", "ali", "SubHub")
    assert uri.startswith("otpauth://totp/SubHub%3Aali?secret=ABC&issuer=SubHub")


def test_recovery_codes_single_use():
    codes = totp.new_recovery_codes()
    hashes = [totp.hash_recovery(c) for c in codes]
    left = totp.consume_recovery(hashes, totp.format_code(codes[0]).lower())  # dash/case insensitive
    assert left is not None and len(left) == len(codes) - 1
    assert totp.consume_recovery(left, codes[0]) is None  # already used
    assert totp.consume_recovery(hashes, "WRONGCODE1") is None


def _g(tags): return SimpleNamespace(extra={"inbound_tags": tags}, name="g")


def test_tags_from_group_shapes():
    assert tags_from_group({"inbound_tags": ["a", "b"]}) == ["a", "b"]
    assert tags_from_group({"inbounds": [{"tag": "x"}, "y"]}) == ["x", "y"]
    assert tags_from_group({"inbounds": {"vless": ["v1"]}}) == ["v1"]
    assert tags_from_group({"id": 1}) == []


def test_pick_group_prefers_tightest_cover():
    wide, tight, other = _g(["a", "b", "c"]), _g(["a", "b"]), _g(["z"])
    assert pick_group([wide, tight, other], {"a", "b"}) is tight
    assert pick_group([other, wide], {"a"}) is wide
    assert pick_group([other, wide], {"nope"}) is other  # no overlap -> first
    assert pick_group([], {"a"}) is None
    assert pick_group([_g([])], set()) is not None
