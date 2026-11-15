"""Pip's shared pure rules: steps, conservative identity, grounded facts, evidence gates."""
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, timedelta


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def strict_json(raw, limit=16000):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    if not isinstance(raw, str) or len(raw) > limit:
        raise ValueError("Response too large")
    try:
        return json.loads(raw, object_pairs_hook=unique)
    except (ValueError, TypeError, RecursionError) as exc:
        raise ValueError("Invalid structured response") from exc


def fallback_steps(title, minutes):
    # Preserve the entire workload, including >300-minute tasks. No invented materials.
    count = max(3, math.ceil((minutes - 30) / 60) + 2)
    base, extra = divmod(minutes - 30, count - 2)
    labels = ["Find a starting point for", "Work through the next part of", "Check progress on"]
    return [{"title": f"{labels[0] if i == 0 else labels[2] if i == count - 1 else labels[1]} {title}"[:240],
             "minutes": 15 if i in (0, count - 1) else base + (i - 1 < extra)} for i in range(count)]


def validate_steps(raw, title, minutes):
    value = strict_json(raw)
    if not isinstance(value, dict) or set(value) != {"steps"} or not isinstance(value["steps"], list):
        raise ValueError("Expected steps")
    steps = value["steps"]
    minimum = max(3, math.ceil(minutes / 60))
    if not minimum <= len(steps) <= max(5, minimum + 2):
        raise ValueError("Invalid step count")
    known_words = set(re.findall(r"\w+", title.casefold()))
    # The model may select meaningful work phases, not invent assignment contents.
    allowed = known_words | set("review identify next part work on check progress finish prepare outline draft revise organize solve practice study write read watch start a an the for of and with remaining material materials mistakes concepts available existing my your important difficult".split())
    seen = set()
    for step in steps:
        if not isinstance(step, dict) or set(step) != {"title", "minutes"}:
            raise ValueError("Invalid step fields")
        text, duration = step["title"], step["minutes"]
        if type(duration) is not int or not 10 <= duration <= 60:
            raise ValueError("Invalid step estimate")
        if not isinstance(text, str) or not 5 <= len(text) <= 240 or text != " ".join(text.split()):
            raise ValueError("Invalid step title")
        if re.search(r"[<>\x00-\x1f]", text) or not re.match(r"^(Review|Identify|Work|Check|Finish|Prepare|Outline|Draft|Revise|Organize|Solve|Practice|Study|Write|Read|Watch|Start)\b", text):
            raise ValueError("Step must be actionable")
        if not set(re.findall(r"\w+", text.casefold())) <= allowed or text.casefold() in seen:
            raise ValueError("Unsupported or repeated step")
        seen.add(text.casefold())
    if sum(s["minutes"] for s in steps) != minutes:
        raise ValueError("Steps must preserve the parent workload")
    return steps


def canonical(title):
    title = title.casefold()
    title = re.sub(r"\b(prepare for|study for|study|prepare)\b", "study", title)
    title = re.sub(r"\b(test|midterm|examination)\b", "exam", title)
    title = re.sub(r"\b(homework|assignment)\b", "coursework", title)
    words = re.findall(r"\w+", title)
    stop = set("i me my the a an to for of need also please oh dont don't forget finish complete do must should have remember by due".split())
    return tuple(sorted(w for w in words if w not in stop))


def duplicate(candidate, existing):
    key = canonical(candidate["title"])
    if len(key) < 2:
        return None
    matches = []
    for task in existing:
        if task.get("parent_task_id") or task.get("status") != "open":
            continue
        if candidate.get("external_id") and task.get("external_item_id"):
            continue  # Separate Canvas IDs are never semantically merged.
        old_due, new_due = task.get("due_date"), candidate.get("due_date")
        if new_due and old_due != new_due:
            continue
        if canonical(task["title"]) == key:
            matches.append(task)
    return matches[0] if len(matches) == 1 else None


def quiet_task(task, raw):
    return not task.get("due_date") and not task.get("due") and task.get("box") not in {"do_now", "quick"} and not re.search(
        r"\b(urgent|asap|important|today|tonight|tomorrow|deadline|soon)\b", raw, flags=re.I)


def eligible(tasks, today, all_steps=False):
    """Parents summarize; only open leaves execute. Window UI shows one next step."""
    children = defaultdict(list)
    by_id = {t["id"]: t for t in tasks}
    for task in tasks:
        if task.get("parent_task_id"):
            children[task["parent_task_id"]].append(task)
    result = []
    for task in tasks:
        if task["status"] != "open" or task["id"] in children or task.get("quiet_filed"):
            continue
        parent = by_id.get(task.get("parent_task_id"))
        if parent:
            if parent["status"] != "open" or parent.get("quiet_filed"):
                continue
            siblings = sorted(children[parent["id"]], key=lambda t: t["step_order"])
            earlier = [s for s in siblings if s["step_order"] < task["step_order"]]
            if not all_steps and any(s["status"] != "done" for s in earlier):
                continue
        result.append(dict(task))
    return result


def supported_patterns(events, today):
    """Only explicitly recorded observations count. Missing logs are never failures."""
    events = [e for e in events if datetime.fromisoformat(e["observed_at"]).date() <= today]
    if len(events) < 8:
        return []
    stamps = [datetime.fromisoformat(e["observed_at"]).date() for e in events]
    if (today - min(stamps)).days < 14 or len(set(stamps)) < 4:
        return []
    groups = defaultdict(dict)
    for event in events:
        if event["kind"] == "complete" and (event.get("actual_minutes") or 0) > 0 and (event.get("estimate_minutes") or 0) > 0:
            groups[event["category"]][event["task_id"]] = event
    result = []
    for category, observations in sorted(groups.items()):
        samples = list(observations.values())
        sample_dates = {datetime.fromisoformat(e["observed_at"]).date() for e in samples}
        if len(samples) < 8 or len(sample_dates) < 4 or (max(sample_dates) - min(sample_dates)).days < 14:
            continue
        total_estimate = sum(e["estimate_minutes"] for e in samples)
        total_actual = sum(e["actual_minutes"] for e in samples)
        over = sum(e["actual_minutes"] > e["estimate_minutes"] for e in samples)
        ratio = total_actual / total_estimate
        if ratio >= 1.25 and over >= math.ceil(len(samples) * .75):
            result.append({"id": "duration-" + category, "kind": "duration", "category": category,
                           "samples": len(samples), "estimated_minutes": total_estimate,
                           "actual_minutes": total_actual, "ratio": round(ratio, 2),
                           "text": f"Across {len(samples)} completed {category.replace('_', ' ')} tasks or steps with logged time, you recorded {total_actual} minutes against {total_estimate} estimated. You could allow more room next time."})
    skips, work = defaultdict(list), defaultdict(list)
    for event in events:
        if event["kind"] == "skip":
            skips[event["category"]].append(event)
        if event["kind"] == "log":
            work[event["category"]].append(event)
    for category, entries in sorted(skips.items()):
        morning = [e for e in entries if 6 <= e["local_hour"] < 12]
        days = {e["observed_at"][:10] for e in morning}
        work_days = {e["observed_at"][:10] for e in work[category]}
        span = (date.fromisoformat(max(days)) - date.fromisoformat(min(days))).days if days else 0
        if len(morning) >= 8 and len(days) >= 4 and span >= 14 and len(work[category]) >= 8 and len(work_days) >= 4 and len(morning) / len(entries) >= .75:
            result.append({"id": "morning-skip-" + category, "kind": "skip_timing", "category": category,
                "samples": len(morning), "dates": len(days), "text":
                f"You chose Not today for {category.replace('_', ' ')} work {len(morning)} times in the morning across {len(days)} dates. If it would help, you could try a different time; this doesn't tell us why you postponed it."})
    return result


OPENINGS = {"plain": "", "gentle": "Let's take one small step. ", "clear": "Here's what I can see. "}


def select_facts(raw, facts):
    """No unrestricted model prose is rendered: only known facts and approved openings."""
    value = strict_json(raw, 4000)
    if not isinstance(value, dict) or set(value) != {"opening", "fact_ids"}:
        raise ValueError("Invalid grounded response")
    ids = value["fact_ids"]
    if not isinstance(value["opening"], str) or value["opening"] not in OPENINGS:
        raise ValueError("Invalid opening")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 2 or any(not isinstance(i, str) or i not in facts for i in ids) or len(set(ids)) != len(ids):
        raise ValueError("Unsupported facts")
    return OPENINGS[value["opening"]] + " ".join(facts[i] for i in ids), ids
