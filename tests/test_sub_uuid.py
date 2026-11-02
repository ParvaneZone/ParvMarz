from app.core.subtokens import is_sub_uuid, issue_subscription_token, new_sub_uuid, verify_subscription_token


def test_new_uuid_is_valid_and_unique():
    a, b = new_sub_uuid(), new_sub_uuid()
    assert a != b and is_sub_uuid(a) and is_sub_uuid(b.upper())


def test_other_token_formats_are_not_uuids():
    compact = issue_subscription_token("ali", 1_700_000_000, 1, user_id=7)
    legacy = issue_subscription_token("ali", 1_700_000_000, 1)
    assert not is_sub_uuid(compact) and not is_sub_uuid(legacy)
    assert verify_subscription_token(compact) == {"id": 7, "v": 1}
    assert verify_subscription_token(new_sub_uuid()) is None


def test_malformed_uuid_rejected():
    assert not is_sub_uuid("") and not is_sub_uuid("not-a-uuid")
    assert not is_sub_uuid(new_sub_uuid() + "x") and not is_sub_uuid("../" + new_sub_uuid())
