from app.core.security import hash_password, verify_password
from app.core.subtokens import issue_subscription_token, verify_subscription_token


def test_password_hashing():
    hashed = hash_password("a-long-test-password")
    assert hashed != "a-long-test-password"
    assert verify_password("a-long-test-password", hashed)
    assert not verify_password("wrong", hashed)


def test_subscription_token_roundtrip_and_tamper():
    token = issue_subscription_token("alice", 123, 4)
    assert verify_subscription_token(token) == {"u": "alice", "c": 123, "v": 4}
    assert verify_subscription_token(token + "x") is None

from app.subscription.merge import deduplicate_links, parse_link

def test_link_deduplication_and_invalid_input():
    one = "vless://1234@example.com:443#first"
    two = "vless://1234@example.com:443#duplicate"
    assert len(deduplicate_links([one, two, "not a link"])) == 1
    assert parse_link(one)["server"] == "example.com"
