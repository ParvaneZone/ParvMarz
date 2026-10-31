from datetime import datetime, timedelta, timezone

def apply_next_plan(current_limit:int|None, used_traffic:int, plan:dict, now:datetime|None=None)->tuple[int|None,datetime,int]:
    now=now or datetime.now(timezone.utc)
    remaining=max((current_limit or 0)-used_traffic,0)
    new_limit=plan.get('data_limit')
    added=remaining if plan.get('add_remaining_traffic') and new_limit is not None else 0
    if new_limit is not None: new_limit+=added
    days=int(plan.get('duration_days',30))
    if days<1 or days>36500: raise ValueError('duration_days must be between 1 and 36500')
    return new_limit,now+timedelta(days=days),added
