#!/usr/bin/env python3
"""Build the solution-review page (an Artifact) from data/ and the pre-screen results.

Usage: python3 tools/review_page.py <prescreen-dir> <out.html> [general-notes.json]

Includes every question with a solution (official ones too) except those fully reviewed: solution.reviewed set
and the hint reviewed (hintReviewed) or absent. Ids in tools/.review/excluded.json are left out as well (the 20
solutions approved before hints existed).
The pre-screen dir holds result-*.json files: [{id, verdict: ok|check|wrong, reason, fix}].
The page stores the reviewer's decisions in the artifact's db, collection "reviews", one document per
question id: {status: ok|problem|unsure|fixed, comment, at, hintStatus: ok|problem|fixed, hintComment}
— plus {claudeNote} / {hintClaudeNote} when a fix awaits re-review.
general-notes.json ({id: summary}) marks solutions changed by a general comment; the page shows the summary.
"""
import base64, glob, html, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import load_course  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SEASON_RANK = {"חורף": 10, "אביב": 30, "קיץ": 50}
MOED_RANK = {"נבצרים": 1, "א": 2, "ב": 3, "ג": 4, "מיוחד": 5}


def exam_label(ex):
    return ex["name"]


def main():
    pre_dir, out = sys.argv[1], sys.argv[2]
    general = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
    pre = {}
    for f in glob.glob(os.path.join(pre_dir, "result-*.json")):
        for r in json.load(open(f, encoding="utf-8")):
            pre[r["id"]] = r
    tax = json.load(open(os.path.join(DATA, "taxonomy.json"), encoding="utf-8"))
    topic_order = {t["name"]: i for i, t in enumerate(tax["topics"])}
    excl_path = os.path.join(ROOT, "tools", ".review", "excluded.json")
    excluded = set(json.load(open(excl_path))) if os.path.exists(excl_path) else set()
    items, images = [], {}
    for f in sorted(glob.glob(os.path.join(DATA, "questions", "*.json"))):
        ex = json.load(open(f, encoding="utf-8"))
        rank = ex["yearNum"] * 100 + SEASON_RANK.get(ex.get("season"), 0) + MOED_RANK.get(ex.get("moed"), 0)
        for q in ex["questions"]:
            s = q.get("solution")
            if not s or q["id"] in excluded or q.get("offSyllabus", {}).get("scope") == "removed":
                continue
            if s.get("reviewed") and (not q.get("hint") or q.get("hintReviewed")):
                continue
            if q.get("image") and q["image"] not in images:
                with open(os.path.join(DATA, "img", q["image"]), "rb") as fh:
                    images[q["image"]] = "data:image/png;base64," + base64.b64encode(fh.read()).decode()
            p = pre.get(q["id"], {})
            items.append({
                "id": q["id"], "exam": exam_label(ex), "rank": rank, "number": q["number"],
                "points": q.get("points"), "topic": q["topic"], "sub": q["sub"], "type": q["type"],
                "text": q["text"], "options": q.get("options"), "correct": q.get("correct"),
                "image": q.get("image"), "notes": q.get("notes"),
                "steps": s["steps"], "answer": s.get("answer"),
                "generalNote": general.get(q["id"], ""),
                "official": bool(s.get("official")), "hint": q.get("hint", ""),
                "pre": p.get("verdict", ""), "preReason": p.get("reason", ""), "preFix": p.get("fix", ""),
            })
    sev = {"wrong": 0, "check": 1}
    items.sort(key=lambda it: (sev.get(it["pre"], 2), topic_order.get(it["topic"], 99), -it["rank"], it["id"]))
    payload = json.dumps({"items": items, "images": images, "topics": [t["name"] for t in tax["topics"]]},
                         ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = open(os.path.join(ROOT, "tools", "review_template.html"), encoding="utf-8").read()
    open(out, "w", encoding="utf-8").write(tpl.replace("/*__DATA__*/", payload).replace("{{COURSE_NAME}}", html.escape(load_course()["courseName"])))
    counts = {k: sum(it["pre"] == k for it in items) for k in ("wrong", "check", "ok", "")}
    print(f"{out}: {len(items)} solutions to review; pre-screen {counts}; {len(payload) / 1e3:.0f} KB of data")


if __name__ == "__main__":
    main()
