from app.jobs.usage_sync import traffic_delta
from app.core.plans import apply_next_plan
from datetime import datetime, timezone

def test_traffic_delta_handles_panel_reset():
    assert traffic_delta(150, 100) == 50
    assert traffic_delta(5, 100) == 0
    assert traffic_delta(0, 0) == 0

def test_next_plan_adds_remaining_traffic():
    now=datetime(2026,1,1,tzinfo=timezone.utc)
    limit, expire, added=apply_next_plan(1000,700,{'data_limit':2000,'duration_days':30,'add_remaining_traffic':True},now)
    assert limit==2300 and added==300
    assert (expire-now).days==30

def test_next_plan_does_not_add_remaining_when_disabled():
    limit, _, added=apply_next_plan(1000,700,{'data_limit':2000,'duration_days':30,'add_remaining_traffic':False})
    assert limit==2000 and added==0
