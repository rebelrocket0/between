"""Pure rules for Between tasks: priority boxes, skips, and Google Tasks payloads.

No network and no database here, so these are easy to test.
"""
from datetime import date, timedelta

BOXES = ("do_now", "plan", "quick", "someday")

# The three categories you actually see: urgent & important, urgent, important.
# Each internal box maps to one category. "someday" (no deadline, not flagged) is Important.
CATEGORY_BY_BOX = {
    "do_now": "urgent_important",
    "quick": "urgent",
    "plan": "important",
    "someday": "important",
}
CATEGORY_NAMES = {
    "urgent_important": "Urgent & important",
    "urgent": "Urgent",
    "important": "Important",
}
CATEGORY_ORDER = ["urgent_important", "urgent", "important"]

# One Google Tasks list per category.
BOX_LABELS = {
    "do_now": "Between: Urgent & important",
    "quick": "Between: Urgent",
    "plan": "Between: Important",
    "someday": "Between: Important",
}

# A task due within this many days is urgent and moves to "do now".
URGENT_WINDOW_DAYS = 2

# After this many skips, a non-urgent task moves to another slot.
SKIPS_BEFORE_MOVE = 2


def valid_date(value):
    """Return the date as YYYY-MM-DD if it is a real ISO date, otherwise None."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def effective_box(box, due_date, today):
    """The box a task belongs in today.

    A task due within the urgent window is always "do now". Otherwise use the box
    Gemini gave it. With no box, a dated task is "plan" and an undated one is "someday".
    """
    due = valid_date(due_date)
    if due and (date.fromisoformat(due) - today).days <= URGENT_WINDOW_DAYS:
        return "do_now"
    if box in BOXES:
        return box
    return "plan" if due else "someday"


def category_for(box, due_date, today):
    """The category a task shows under today."""
    return CATEGORY_BY_BOX[effective_box(box, due_date, today)]


def should_move_after_skip(skips, box):
    """Non-urgent tasks get moved after enough skips. Do-now tasks never move."""
    return box in ("plan", "someday", "quick") and (skips or 0) >= SKIPS_BEFORE_MOVE


def google_task_body(title, box, due_date, minutes, area, status="needsAction"):
    """The body Google Tasks expects for one task."""
    notes_parts = [part for part in (area, f"{minutes} min" if minutes else None) if part]
    body = {
        "title": title,
        "status": status,
        "notes": " · ".join(notes_parts) if notes_parts else BOX_LABELS[box],
    }
    due = valid_date(due_date)
    if due:
        # Google Tasks keeps only the date part of a due time.
        body["due"] = f"{due}T00:00:00.000Z"
    return body


# Calendar blocks: how the day gets filled with planned tasks.
BOX_ORDER = {"do_now": 0, "quick": 1, "plan": 2, "someday": 3}
BLOCK_BUFFER_MINUTES = 5
DEFAULT_BLOCK_MINUTES = 20
MIN_BLOCK_MINUTES = 10
MAX_BLOCK_MINUTES = 90
MAX_SOMEDAY_BLOCKS = 2


def plan_blocks(gaps, tasks):
    """Place tasks into free time.

    gaps: list of (start, end) datetimes, in order.
    tasks: dicts with id, title, box, minutes.
    Do-now tasks go first, then small tasks first within each box. Returns
    [{task_id, title, start, end}]. Tasks that don't fit are left out.
    """
    ordered = sorted(
        tasks,
        key=lambda t: (
            BOX_ORDER.get(t["box"], 9),
            # Tasks skipped often go behind the others in their box, so something else gets the slot.
            1 if should_move_after_skip(t.get("skips"), t["box"]) else 0,
            t.get("minutes") or DEFAULT_BLOCK_MINUTES,
        ),
    )
    free = [[start, end] for start, end in gaps if end > start]
    blocks = []
    someday_count = 0
    for task in ordered:
        if task["box"] == "someday":
            if someday_count >= MAX_SOMEDAY_BLOCKS:
                continue
        length = min(MAX_BLOCK_MINUTES, max(MIN_BLOCK_MINUTES, task.get("minutes") or DEFAULT_BLOCK_MINUTES))
        need = timedelta(minutes=length)
        for slot in free:
            if slot[1] - slot[0] >= need:
                start = slot[0]
                end = start + need
                blocks.append({"task_id": task["id"], "title": task["title"], "start": start, "end": end})
                slot[0] = end + timedelta(minutes=BLOCK_BUFFER_MINUTES)
                if task["box"] == "someday":
                    someday_count += 1
                break
    return blocks


def validate_plan(raw_plan, gaps, tasks):
    """Keep only the parts of an AI-made day plan that are safe to use.

    raw_plan: [{"task_id", "start": "HH:MM", "reason"}] as Gemini returns it.
    gaps: (start, end) datetimes. tasks: dicts with id, box, minutes.
    A block is kept only if it uses a real open task once, starts at a valid time,
    and fits entirely inside free time. Returns blocks shaped like plan_blocks,
    plus a reason.
    """
    if not isinstance(raw_plan, list):
        return []
    known = {task["id"]: task for task in tasks}
    free = [[start, end] for start, end in gaps if end > start]
    blocks = []
    used = set()
    someday_count = 0
    for item in raw_plan[:20]:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        if isinstance(task_id, bool) or task_id not in known or task_id in used:
            continue
        task = known[task_id]
        if task.get("box") == "someday" and someday_count >= MAX_SOMEDAY_BLOCKS:
            continue
        try:
            hour, minute = (int(part) for part in str(item.get("start")).split(":"))
        except (TypeError, ValueError):
            continue
        if not (0 <= hour < 24 and 0 <= minute < 60):
            continue
        length = min(MAX_BLOCK_MINUTES, max(MIN_BLOCK_MINUTES, task.get("minutes") or DEFAULT_BLOCK_MINUTES))
        need = timedelta(minutes=length)
        for slot in list(free):
            start = slot[0].replace(hour=hour, minute=minute, second=0, microsecond=0)
            end = start + need
            if start < slot[0] or end > slot[1]:
                continue
            reason = " ".join(str(item.get("reason") or "").split())[:160]
            blocks.append({"task_id": task_id, "title": task["title"], "start": start, "end": end, "reason": reason})
            used.add(task_id)
            if task.get("box") == "someday":
                someday_count += 1
            free.remove(slot)
            before = [slot[0], start - timedelta(minutes=BLOCK_BUFFER_MINUTES)]
            after = [end + timedelta(minutes=BLOCK_BUFFER_MINUTES), slot[1]]
            free.extend(piece for piece in (before, after) if piece[1] > piece[0])
            break
    return sorted(blocks, key=lambda block: block["start"])


PLAN_WINDOW_DAYS = 7


def within_plan_window(due_date, today, days=PLAN_WINDOW_DAYS):
    """True if a task belongs in today's plan: no deadline, or due within the window."""
    due = valid_date(due_date)
    if not due:
        return True
    return (date.fromisoformat(due) - today).days <= days


PLAN_HORIZON_DAYS = 14
SESSION_MINUTES = 60
MAX_DAY_TASK_MINUTES = 240


def spread_sessions(tasks, day_gaps, today, horizon_days=PLAN_HORIZON_DAYS):
    """Spread each task's work over the days before it is due.

    tasks: dicts with id, title, box, due (YYYY-MM-DD or None), minutes (total estimate).
    day_gaps: {date: [(start, end) datetimes]} of free time for each day.
    Rules: earliest deadline first. A task gets at most one session per day, so work
    spreads out. A day holds at most MAX_DAY_TASK_MINUTES of task time.
    Returns (blocks, unplaced_task_ids). Blocks are sorted by start time.
    """
    slots = {day: [[start, end] for start, end in gaps if end > start] for day, gaps in day_gaps.items()}
    used_minutes = {day: 0 for day in day_gaps}
    last_day = today + timedelta(days=horizon_days)

    def urgency(task):
        return (valid_date(task.get("due")) or "9999-12-31", BOX_ORDER.get(task.get("box"), 9))

    blocks = []
    unplaced = []
    for task in sorted(tasks, key=urgency):
        due = valid_date(task.get("due"))
        deadline = min(date.fromisoformat(due), last_day) if due else last_day
        deadline = max(deadline, today)
        remaining = task.get("minutes") or DEFAULT_BLOCK_MINUTES
        days_used = set()
        while remaining > 0:
            placed = False
            for day in sorted(slots):
                if day < today or day > deadline or day in days_used:
                    continue
                room = MAX_DAY_TASK_MINUTES - used_minutes[day]
                length = min(SESSION_MINUTES, remaining, room)
                if length < MIN_BLOCK_MINUTES:
                    continue
                need = timedelta(minutes=length)
                for slot in list(slots[day]):
                    start = slot[0]
                    end = start + need
                    if end > slot[1]:
                        continue
                    blocks.append({
                        "task_id": task["id"],
                        "title": task["title"],
                        "box": task.get("box"),
                        "due": due,
                        "start": start,
                        "end": end,
                    })
                    slots[day].remove(slot)
                    before = [slot[0], start - timedelta(minutes=BLOCK_BUFFER_MINUTES)]
                    after = [end + timedelta(minutes=BLOCK_BUFFER_MINUTES), slot[1]]
                    slots[day].extend(piece for piece in (before, after) if piece[1] > piece[0])
                    used_minutes[day] += length
                    remaining -= length
                    days_used.add(day)
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                unplaced.append(task["id"])
                break
    return sorted(blocks, key=lambda block: block["start"]), unplaced


WEEKDAYS = {name: i for i, name in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}
WEEKDAYS.update({name[:3]: i for name, i in list(WEEKDAYS.items())})


def date_from_words(text, today):
    """Turn due words into a date: 'Friday', 'tomorrow', 'today', 'next Monday', or YYYY-MM-DD. None if unclear."""
    if not text:
        return None
    lowered = " ".join(str(text).lower().replace(",", " ").split())
    iso = valid_date(lowered[:10])
    if iso:
        return iso
    if "today" in lowered or "tonight" in lowered:
        return today.isoformat()
    if "tomorrow" in lowered:
        return (today + timedelta(days=1)).isoformat()
    words = lowered.replace("by ", " ").replace("due ", " ").replace("on ", " ").split()
    for word in words:
        if word in WEEKDAYS:
            ahead = (WEEKDAYS[word] - today.weekday()) % 7
            if ahead == 0 or "next" in words:
                ahead += 7 if ahead == 0 or "next" in words else 0
            return (today + timedelta(days=ahead)).isoformat()
    return None
