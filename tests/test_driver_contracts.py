import pytest

from app.drivers.base import AccessPlan
from app.drivers.factory import build_driver


def test_access_plan_maps_to_panel_specific_access_objects():
    plan = AccessPlan.from_spec({
        "inbounds": {"vless": ["vless-a"]}, "service_id": 8, "group_ids": [3, 4]
    })
    assert plan.for_panel("marzban") == {"inbounds": {"vless": ["vless-a"]}}
    assert plan.for_panel("rebecca") == {"service_id": 8}
    assert plan.for_panel("pasarguard") == {"group_ids": [3, 4]}


def test_access_plan_rejects_missing_rebecca_service_or_pasarguard_group():
    with pytest.raises(ValueError, match="service_id"):
        AccessPlan().for_panel("rebecca")
    with pytest.raises(ValueError, match="group_ids"):
        AccessPlan().for_panel("pasarguard")


@pytest.mark.parametrize("panel_type,expected", [
    ("marzban", True), ("marzdar", True), ("marzyar", True),
    ("pasarguard", True), ("rebecca", True),
])
def test_driver_capabilities_are_exposed(panel_type, expected):
    driver = build_driver(panel_type, "https://panel.example", {}, verify_ssl=False)
    assert driver.capabilities["users.create"] is expected
    assert driver.capabilities["users.list"] is True
    assert driver.verify_ssl is False


def test_marzdar_variant_only_exposes_variant_specific_actions():
    marzban = build_driver("marzban", "https://panel.example", {})
    marzdar = build_driver("marzdar", "https://panel.example", {})
    assert marzban.capabilities["admins.manage"] is False
    assert marzdar.capabilities["admins.manage"] is False
    assert marzdar.capabilities["admins.remote_owner"] is True
    assert marzdar.capabilities["admins.users_status"] is True
    assert marzdar.capabilities["admins.usage"] is False
