"""One shared clock for the whole app.

Streamlit Community Cloud runs in UTC, while a laptop runs in local time. Using
datetime.now() directly made the "today" date differ between the two (before
07:00 in Vietnam the cloud server is still on yesterday). Vietnam has no
daylight saving, so a fixed UTC+7 offset is enough and needs no extra package.
"""

import datetime

VIETNAM_TIME = datetime.timezone(datetime.timedelta(hours=7))


def now() -> datetime.datetime:
    return datetime.datetime.now(VIETNAM_TIME)
