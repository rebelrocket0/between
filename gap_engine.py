"""Gap engine: decides which tasks fit a free window.

Pure functions only. No database or network calls, so every rule can be tested directly.
Tasks are plain dicts with: id, title, status, duration_minutes, logged_minutes, due_text.
"""

MIN_SESSION = 15   # shortest useful block of time
MAX_SESSION = 90   # longest single sitting before a break makes sense
SHORT_WINDOW = 60  # below this, small tasks go first


def remaining_minutes(task):
    """Minutes left on a task, or None if it has no estimate."""
    estimate = task.get("duration_minutes")
    if not estimate:
        return None
    logged = int(task.get("logged_minutes") or 0)
    return max(int(estimate) - logged, 0)


def is_urgent(task):
    # Dates aren't parsed yet. Any due text counts as urgent.
    return bool(task.get("due_text"))


def _sort_key(task, window):
    left = remaining_minutes(task)
    fits = left <= window
    # Urgent first. Then tasks that finish inside the window beat partial sessions.
    # Short windows favor small tasks. Longer windows favor bigger tasks so the time is used well.
    size = left if window < SHORT_WINDOW else -left
    return (0 if is_urgent(task) else 1, 0 if fits else 1, size, task.get("id", 0))


def fits_window(tasks, window):
    """Open tasks whose remaining time fits inside the window, largest first."""
    window = int(window)
    candidates = [
        t for t in tasks
        if t.get("status", "open") == "open"
        and (remaining_minutes(t) or 0) > 0
        and remaining_minutes(t) <= window
    ]
    return sorted(candidates, key=lambda t: _sort_key(t, window))


def plan_window(tasks, window):
    """Suggest sessions that fill the window without going over.

    Each suggestion: {task_id, title, minutes, kind}.
    kind is "finish" when the task completes in this block, "session" when it only makes progress.
    """
    window = int(window)
    if window < MIN_SESSION:
        return []

    open_tasks = [
        t for t in tasks
        if t.get("status", "open") == "open" and (remaining_minutes(t) or 0) > 0
    ]
    open_tasks.sort(key=lambda t: _sort_key(t, window))

    plan = []
    left_window = window
    for task in open_tasks:
        if left_window < MIN_SESSION:
            break
        left = remaining_minutes(task)
        if left <= left_window:
            minutes, kind = left, "finish"
        else:
            minutes = min(left_window, MAX_SESSION)
            kind = "session"
            if minutes < MIN_SESSION:
                continue
        plan.append({
            "task_id": task.get("id"),
            "title": task.get("title"),
            "minutes": minutes,
            "kind": kind,
        })
        left_window -= minutes
    return plan
