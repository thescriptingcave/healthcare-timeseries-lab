"""Build the M10 business-question tutorial notebooks.

Generates, from the ``sql/dql`` lesson library and the live lakehouse:

* ``notebooks/tutorial_business_beginner.ipynb``
* ``notebooks/tutorial_business_intermediate.ipynb``
* ``notebooks/tutorial_business_advanced.ipynb``

Usage::

    uv run python scripts/build_m10_notebooks.py

The notebooks are meant to be executed (``nbconvert --execute --inplace``)
with the compose stack up so the committed files carry rendered outputs.
"""

import nbformat

KERNEL = {"name": "python3", "display_name": "Python 3", "language": "python"}


def md(text: str):
    return nbformat.v4.new_markdown_cell(text)


def code(src: str):
    return nbformat.v4.new_code_cell(src)


def save(name: str, cells):
    notebook = nbformat.v4.new_notebook(
        metadata={"kernelspec": KERNEL, "language_info": {"name": "python"}},
        cells=cells,
    )
    with open(f"notebooks/{name}", "w", encoding="utf-8") as handle:
        nbformat.write(notebook, handle)
    return name


BOOTSTRAP = """\
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from healthcare_timeseries_lab.tutorials import (
    Lesson,
    load_lesson_sql,
    run_lesson,
    run_live,
    ward_names,
)

WARD = ward_names()
NAOMI = "55555555-5555-5555-5555-555555555555"
COLE = "66666666-6666-6666-6666-666666666666"
IVY = "77777777-7777-7777-7777-777777777777"


def lesson(stem: str) -> Lesson:
    tier = {"b": "beginner", "i": "intermediate", "a": "advanced"}[stem[0]]
    return Lesson(tier=tier, stem=stem)


def show_sql(stem: str) -> None:
    print(load_lesson_sql(lesson(stem)))


def tz_free(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series)
    if values.dt.tz is None:
        values = values.dt.tz_localize("UTC")
    return values.dt.tz_convert("UTC").dt.tz_localize(None)


pd.set_option("display.max_rows", 120)
pd.set_option("display.width", 140)
plt.rcParams["figure.figsize"] = (11, 4.2)
plt.rcParams["figure.dpi"] = 110
plt.rcParams["axes.grid"] = True
plt.rcParams["grid.alpha"] = 0.3
"""

INTRO = """\
## Clinical Analytics 101 — Milestone 10

This tutorial series teaches **time-series SQL**, **CTEs** and **window
functions** the way analytics happens in a real organisation: someone asks a
*business question*, and you shape the data to answer it.

| Notebook | You will learn | Business questions |
|---|---|---|
| **Beginner** | JOINs, `date_trunc` time buckets, CTEs | Who is on the ward? Build the hourly handoff report. Flag the patient who needs attention at 04:00. |
| **Intermediate** | `LAG`/`LEAD`, moving averages, `RANK`/`NTILE` | When did the deterioration start? Is that spike real or device noise? Where does a reading sit in its patient's distribution? |
| **Advanced** | gap-and-islands episodes, sessionization, truth audits | How many *distinct* episodes? How do hundreds of alarm ticks become 2 alarm events? Can we trust the monitor? |

### How a lesson works

Every lesson is one heavily-commented SQL file in `sql/dql/<tier>/`. In each
lesson you read the business question, **read the SQL file** (it is printed),
**run it against the live Trino lakehouse**, read the answer, and see it on a
chart. With the compose stack down, the lesson cells fall back to the
pre-rendered parquet snapshots in `datasets/m10/lessons/`.

### The dataset

A tiny ward simulated by this repo (5-second telemetry through the Milestone 8
device layer):

| Patient | MRN | Story | Admitted | Monitored |
|---|---|---|---|---|
| **Naomi Brooks** | MRN-000101 | Desaturation (hypoxemia) | 00:00 | 6 h |
| **Cole Freeman** | MRN-000102 | Tachycardia | 00:30 | 5 h |
| **Ivy Watson** | MRN-000103 | Stable control | 01:00 | 3 h |

Patient demographics + admissions live in **MySQL** (`mysql.clinical`), the
observed vitals in the **Iceberg lakehouse** (`lake.lakehouse.vitals`), and
the exact simulated physiology in `lake.lakehouse.vitals_truth` (used in the
advanced notebook). `Ava Chen` and `Marcus Lee` are two legacy patients left
from earlier milestones — a gift, because real databases always contain older,
messier history.

> Rebuild or check this dataset anytime with
> `uv run python scripts/generate_m10_dataset.py`.
"""


def lesson_block(stem: str, note: str = "") -> list:
    return [
        md(f"**1. Read the SQL for `{stem}`** — the file comments explain the business question and how the query is assembled, piece by piece."),
        code(f'show_sql("{stem}")'),
        md(f"**2. Run it against the lakehouse.**{note}"),
        code(f'df = run_lesson(lesson("{stem}"))\ndisplay(df)'),
    ]


# ---------------------------------------------------------------------------
# Beginner
# ---------------------------------------------------------------------------


def build_beginner() -> str:
    cells = [
        md(INTRO),
        code(BOOTSTRAP),
        md(
            """\
# Beginner — know your ward

Three questions, each adding one skill:

* **B1** INNER JOIN — "who was on the ward on January 1st?"
* **B2** time bucketing + a CTE — "build the hourly handoff report."
* **B3** aggregate-then-filter + LEFT JOIN — "which patient needs attention at 04:00?"

Nail these and you can answer most "give me a summary" asks in any
organisation — the hard part was never the keyword, it was shaping the data.
"""
        ),
        md(
            """\
### B1 — "Who was on the ward on January 1st?"

The charge nurse wants one list of every patient admitted that day: names,
MRNs, demographics and each admission window.

*What this teaches:* reading tables, an **INNER JOIN** between `patients` and
`encounters` in the same MySQL catalog, and a stable `ORDER BY`.

**Run the lesson** — first read its SQL, then execute it:
"""
        ),
        *lesson_block("b1_ward_census"),
        md(
            """\
**Reading the result.** Five rows:

* `Ava Chen` and `Marcus Lee` are the **legacy** Milestone 5 patients — their
  encounters are `COMPLETED`.
* Naomi, Cole and Ivy are this episode's ward. Naomi is `ACTIVE` with `NULL`
  in `ended_at`: she is *still admitted*. A `NULL` discharge time is
  information, not an error.

An **INNER JOIN** keeps only rows present on both sides — a patient without an
encounter vanishes. That is what we want here, and exactly what we
deliberately invert in B3.
"""
        ),
        code(
            """\
gantt = run_lesson(lesson("b1_ward_census")).copy()
start = tz_free(gantt["admitted_at"])
end = tz_free(gantt["ended_at"]).fillna(pd.Timestamp("2026-01-01 06:00:00"))

fig, ax = plt.subplots(figsize=(11, 3.6))
ordered = gantt.sort_values("admitted_at").reset_index(drop=True)
for i in range(len(ordered)):
    hours = (end.iloc[i] - start.iloc[i]).total_seconds() / 3600
    ax.barh(i, hours, left=start.iloc[i], height=0.6, color="#1f77b4", alpha=0.85)
ax.set_yticks(range(len(ordered)))
ax.set_yticklabels(ordered["full_name"])
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.set_xlabel("time on 2026-01-01")
ax.set_title("Admission windows - who is on the ward, and for how long?")
ax.axvline(pd.Timestamp("2026-01-01 03:00:00"), color="#d62728", ls="--", lw=2)
ax.set_xlim(pd.Timestamp("2026-01-01 00:00:00"), pd.Timestamp("2026-01-01 06:00:00"))
plt.tight_layout()
plt.show()
"""
        ),
        md(
            """\
**Your turn:**

1. Add `WHERE e.status = 'ACTIVE'` to B1 — who is currently admitted?
2. Add `WHERE p.age >= 50` — patients over 50.
3. Temporarily swap the join to a `LEFT JOIN` and watch Ava/Marcus change —
   you'll understand the difference fully by B3.

### B2 — "Build the hourly handoff report"

For every monitored patient, what did each vital average in each clock-hour?
This is the ward's shift-change handoff sheet.

*What this teaches:* the heart of time-series SQL — **`date_trunc('hour', ...)`**
buckets timestamps into clock-hours (change the unit and you have every other
periodic report), `GROUP BY patient + hour` with `AVG()` per vital, a **CTE**
(`WITH hourly AS (...)`) so the final SELECT is a clean read, and a
**cross-catalog JOIN** (vitals in `lake`, demographics in `mysql`).
"""
        ),
        *lesson_block("b2_hourly_handoff"),
        md(
            """\
**Reading the result.** 17 rows — and the naive guess is 16 (Naomi 6 hours +
Cole 6 + Ivy 4). The 17th row is Naomi's **06:00 bucket with a single
reading**: her telemetry stops at exactly `06:00:00` and `date_trunc` buckets
that boundary event into the *next* hour. Boundary events are a fact of life —
a good analyst spots and handles them deliberately.

The `avg_spo2` column carries the story: Naomi's hourly average dives to ~89 in
the 02:00 and 03:00 buckets while Cole (97) and Ivy (99) never waver.
"""
        ),
        code(
            """\
handoff = run_lesson(lesson("b2_hourly_handoff")).copy()
handoff["hour"] = tz_free(handoff["shift_hour"])

fig, (ax_spo2, ax_hr) = plt.subplots(1, 2, figsize=(12, 4))
for name in WARD.values():
    one = handoff[handoff["full_name"] == name].sort_values("hour")
    label = name.split()[0]
    ax_spo2.plot(one["hour"], one["avg_spo2"], marker="o", label=label)
    ax_hr.plot(one["hour"], one["avg_heart_rate"], marker="o", label=label)

ax_spo2.axhline(95, color="#d62728", ls="--", lw=1, alpha=0.8)
ax_spo2.set_ylabel("mean SpO2 (%)")
ax_spo2.set_title("Hourly SpO2 - Naomi's desaturation is obvious")
ax_spo2.legend(ncol=3)

ax_hr.set_ylabel("mean heart rate (bpm)")
ax_hr.set_title("Hourly heart rate - Cole runs hot then recovers")
ax_hr.legend(ncol=3)

for axis in (ax_spo2, ax_hr):
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.tight_layout()
plt.show()
"""
        ),
        md(
            """\
**Your turn:**

1. Change `date_trunc('hour', ...)` to `'minute'` in B2 and re-run — the
   report inflates ~60x. That knob is your sampling rate.
2. Confirm Ivy has ~720 readings/hour (60 min x 12 ticks, minus dropouts).
3. Extend the CTE with the per-hour *max minus min* SpO2 spread — the next
   notebook computes the same idea with window functions and throws in `LAG`
   for free.

### B3 — "Which patient needs attention at 04:00?"

Which monitored patients spent the previous hour (03:00-04:00) with an
**average SpO2 below 95%**?

*What this teaches:* you cannot put `AVG()` in a `WHERE` clause — aggregates
are computed first, filtered after (we shape the aggregate in a CTE and filter
in the outer query), and **LEFT JOIN vs INNER JOIN**: Marcus Lee exists in the
clinical store but has *no telemetry at all*. An INNER JOIN would quietly hide
him; a LEFT JOIN keeps the row and marks the missing data `NULL` — and that
absence is itself the finding.
"""
        ),
        *lesson_block("b3_flag_attention"),
        md(
            """\
**Reading the result.** Two patients sit below 95%:

* **Naomi Brooks — avg 89** across 03:00-04:00. That's the desaturation. Cole
  (97) and Ivy (99) are fine.
* **Ava Chen — avg 88.** The *legacy* patient's older trace also dipped. Real
  organisations accumulate messy history; a good analyst asks "same episode or
  a different run?" before reporting it as today's event.
* **Marcus Lee — `NULL`.** Not a missing value — *no measurements exist*. The
  LEFT JOIN preserved the row so the nurse sees "patient known, telemetry
  absent". That distinction is why LEFT JOIN exists.
"""
        ),
        code(
            """\
flags = run_lesson(lesson("b3_flag_attention")).copy()
flags = flags.sort_values("avg_spo2", na_position="last").reset_index(drop=True)

fig, ax = plt.subplots(figsize=(11, 3.8))
colors = ["#d62728" if (value is not None and value < 95) else "#7f7f7f"
          for value in flags["avg_spo2"]]
ax.barh(range(len(flags)), flags["avg_spo2"].fillna(0), color=colors, height=0.6)
ax.set_yticks(range(len(flags)))
ax.set_yticklabels(flags["full_name"] + "  " + flags["mrn"].fillna(""))
ax.axvline(95, color="grey", ls="--", lw=1)
ax.set_xlabel("average SpO2 (%) 03:00-04:00")
ax.set_title("Overnight flags - below 95% needs a hand-off note")
ax.set_xlim(80, 102)
plt.tight_layout()
plt.show()
"""
        ),
        md(
            """\
**Your turn:**

1. Swap the LEFT JOIN to an INNER JOIN in
   `sql/dql/beginner/b3_flag_attention.sql` and re-run — Marcus disappears.
   That is the entire lesson, hands-on.
2. Move the threshold to `97` and watch Cole get flagged. Thresholds are a
   business decision, not a math law.
3. What if a patient had only *one* reading in the hour? Should that count as
   an "average"?

## End of the beginner course

You can now shape a query, join two tables, bucket time, compose with CTEs, and
aggregate-then-filter — a complete skill set for summary reports.

Before the intermediate notebook, look at Naomi's raw SpO2 curve in
`lake.lakehouse.vitals` and notice how twitchy it is. That noise is exactly
what the next three lessons are about.
"""
        ),
    ]
    return save("tutorial_business_beginner.ipynb", cells)


# ---------------------------------------------------------------------------
# Intermediate
# ---------------------------------------------------------------------------


def build_intermediate() -> str:
    cells = [
        md(INTRO),
        code(BOOTSTRAP),
        md(
            """\
# Intermediate — spot the turning points

The beginner notebook showed you the *what*: summaries. This one is about the
*when* and the *how much*. Window functions answer three classic questions
about a stream:

1. What happened right before this row? → `LAG`/`LEAD`
2. What is the local trend over a window? → moving averages
3. Where does this row rank in its own history? → `RANK`/`NTILE`

> **The one big idea.** A window function computes a value *per row* over a
> moving set of neighboring rows — unlike `GROUP BY` it does NOT collapse your
> rows. That's why you can still see every 5-second tick *and* its surrounding
> context — and why you can't filter a window inside its own SELECT. You wrap
> it in a CTE (you already know CTEs!).
"""
        ),
        md(
            """\
### I1 — "When did Naomi start to deteriorate?"

Pinpoint the reading where Naomi's SpO2 first crossed **below 94%** after being
at/above it, and show the reading before and after.

*What this teaches:* `LAG(value, 1) OVER (PARTITION BY patient_id ORDER BY
event_time)` reads the *previous row* in the window; a **state transition**
`previous >= 94 AND current < 94` finds the START of an event without an event
table. Change the threshold in the SQL file to `90` and watch the crossing move
toward the deep plateau.
"""
        ),
        *lesson_block("i1_first_drop"),
        md(
            """\
**Reading the result.** The *first* crossing below 94% is at **02:33:20**
(94 → 93). But the table returns 22 such crossings. Why?

The plateau is deep, but the *shoulders* of the desaturation pass right through
the 94% line, and the monitor adds noise (Milestone 8). Each flicker above 94
registers as a new "crossing" — a raw transition query tells you where the
event started, but it **over-counts events**. That's exactly the problem the
advanced notebook's *gap-and-islands* pattern solves.

First, let's see the whole night: (this bonus cell runs **live** against the
lakehouse)
"""
        ),
        code(
            """\
trace = run_live(
    "SELECT event_time, spo2_pct FROM lake.lakehouse.vitals "
    f"WHERE patient_id = '{NAOMI}' ORDER BY event_time"
)
trace["t"] = tz_free(trace["event_time"])
minute = trace.set_index("t")["spo2_pct"].resample("1min").median()

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(minute.index, minute.values, color="#1f77b4", lw=1.6)
ax.axhline(94, color="#d62728", ls="--", lw=1.2)
ax.axhline(90, color="#ff7f0e", ls="--", lw=1.2, alpha=0.7)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.set_xlabel("time")
ax.set_ylabel("minute-median SpO2 (%)")
ax.set_title("Naomi - the 01:12 spike is noise; the 02:33 to 04:00 dip is the event")
plt.tight_layout()
plt.show()
"""
        ),
        code(
            """\
big = run_live(
    "WITH d AS ("
    "  SELECT event_time, spo2_pct,"
    "         spo2_pct - LAG(spo2_pct, 1) OVER "
    "           (PARTITION BY patient_id ORDER BY event_time) AS delta"
    "  FROM lake.lakehouse.vitals"
    f"  WHERE patient_id = '{NAOMI}'"
    ") "
    "SELECT event_time, ROUND(delta, 2) AS drop_pct "
    "FROM d WHERE delta IS NOT NULL ORDER BY delta ASC LIMIT 1"
)
display(big)
"""
        ),
        md(
            """\
**There's the trap.** The single biggest one-tick drop is **-3.0% at 01:12:45 —
over an hour BEFORE Naomi's real event.** It's a sensor artifact, and
`ORDER BY delta ASC LIMIT 1` confidently reports it as the "worst moment".
Raw extremes in noisy data are nearly always artifacts — which brings us to I2.
"""
        ),
        md(
            """\
### I2 — "Is that spike real, or device noise?"

Compare Naomi's **raw** SpO2 to a **smoothed** line — a centered 7-reading
moving average (≈ ±15 s at a 5 s cadence) — to separate transient spikes from a
genuine sustained trend. Ivy joins as the stable control.

*What this teaches:* a **moving-average window** — `AVG(spo2_pct) OVER (PARTITION
BY patient_id ORDER BY event_time ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING)`.
Smoothing trades sharpness for stability: spikes vanish, trends survive.
"""
        ),
        *lesson_block("i2_moving_average"),
        md(
            """\
**Reading the result.** `deviation_from_average` shows how far each tick sits
from its own local window. On the raw curve Ivy's monitor even reports an
*impossible* **102% SpO2** (noise + rounding) — the smoothing window ages that
artifact out.
"""
        ),
        code(
            """\
ma = run_lesson(lesson("i2_moving_average")).copy()
ma["t"] = tz_free(ma["event_time"])

fig, (ax_n, ax_i) = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
for axis, patient, label in (
    (ax_n, "Naomi Brooks", "Naomi"),
    (ax_i, "Ivy Watson", "Ivy"),
):
    one = ma[ma["full_name"] == patient].sort_values("t")
    window_start = one["t"].min() + pd.Timedelta(hours=2, minutes=30)
    window_end = window_start + pd.Timedelta(minutes=20)
    seg = one[(one["t"] >= window_start) & (one["t"] < window_end)]
    axis.plot(seg["t"], seg["raw_spo2"], ".", color="#1f77b4", ms=3, alpha=0.5)
    axis.plot(seg["t"], seg["spo2_ma"], color="#d62728", lw=1.8)
    axis.set_title(f"{label} - raw vs smoothed")
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax_n.set_ylabel("SpO2 (%)")
plt.tight_layout()
plt.show()
"""
        ),
        code(
            """\
counts = run_live(
    "WITH m AS ("
    "  SELECT spo2_pct,"
    "         AVG(spo2_pct) OVER (PARTITION BY patient_id ORDER BY event_time "
    "           ROWS BETWEEN 3 PRECEDING AND 3 FOLLOWING) AS spo2_ma"
    "  FROM lake.lakehouse.vitals"
    f"  WHERE patient_id = '{NAOMI}') "
    "SELECT"
    "  SUM(CASE WHEN spo2_pct < 94 THEN 1 ELSE 0 END) AS raw_below_94,"
    "  SUM(CASE WHEN spo2_ma  < 94 THEN 1 ELSE 0 END) AS smoothed_below_94"
    " FROM m"
)
display(counts)
"""
        ),
        md(
            """\
**The payoff.** A raw reading dips below 94% **hundreds** of times as noise
re-crosses the line; the 7-reading moving average crosses it only a **handful**
of times near the actual event. That's why smoothing exists: it answers "is
there a *sustained* problem here?" without tuning the alarm to every twitch.

### I3 — "Where does a reading sit in its patient's distribution?"

Label every reading with where it falls in **that patient's own** SpO2
distribution: its worst-rank (1 = the lowest reading of the stay) and its
decile (1 = worst 10%).

*What this teaches:* `RANK()` (ties share a rank — the lowest readings may be a
whole *set* of equal values), `NTILE(10)` (ten equal slices), and the
CTE-wrap rule — you can't filter `RANK()` inside its own SELECT.
"""
        ),
        *lesson_block("i3_worst_ranked"),
        md(
            """\
**Reading the result.** The three worst readings per patient:

* Naomi's worst cluster around **88-89** — and with ~430 readings in *every*
  decile, her worst decile is hundreds of ticks. A reading of 89 isn't just
  low in absolute terms; it's in Naomi's **own worst few percent**.
* Cole and Ivy's "worst three" are ~95-97 and 99 — for healthy patients their
  personal worst is still clinically fine. Ranking against the *patient's own*
  distribution turns a raw number into a personalized flag.
"""
        ),
        code(
            """\
deciles = run_live(
    "WITH dist AS ("
    "  SELECT patient_id, spo2_pct,"
    "         NTILE(10) OVER (PARTITION BY patient_id ORDER BY spo2_pct ASC) AS d"
    "  FROM lake.lakehouse.vitals"
    f"  WHERE patient_id IN ('{NAOMI}', '{IVY}')) "
    " SELECT patient_id, d, ROUND(AVG(spo2_pct), 1) AS mean_spo2, COUNT(*) AS n"
    " FROM dist GROUP BY 1, 2 ORDER BY 1, 2"
)
deciles["name"] = deciles["patient_id"].map(WARD)

fig, ax = plt.subplots(figsize=(11, 4.5))
for offset, name in ((-0.2, "Naomi Brooks"), (0.2, "Ivy Watson")):
    one = deciles[deciles["name"] == name].sort_values("d")
    ax.bar(one["d"] + offset, one["mean_spo2"], width=0.4, alpha=0.8, label=name.split()[0])
ax.set_xticks(range(1, 11))
ax.set_xlabel("decile (1 = worst 10% of readings)")
ax.set_ylabel("mean SpO2 (%) in decile")
ax.set_title("Every reading labeled against its patient's own distribution")
ax.legend()
plt.tight_layout()
plt.show()
"""
        ),
        md(
            """\
**Your turn.**

1. In `i1_first_drop.sql` change the threshold from `94` to `90` — the first
   crossing moves to ~02:54 and the transition count collapses. Thresholds
   change the number of "events" you see.
2. In `i2_moving_average.sql` change the window to `ROWS BETWEEN 9 PRECEDING
   AND 9 FOLLOWING`. The line gets smoother — and slower to react. That lag is
   the price of calm.
3. In `i3_worst_ranked.sql` switch `RANK()` to `DENSE_RANK()` and diff the two
   worst lists. When your values are repeated, dense ranks behave differently.

## End of the intermediate course

You can now see time: `LAG`/`LEAD` give you before/after, moving averages give
you sustained trends, and `RANK`/`NTILE` give you personalized flags. The
advanced notebook turns these primitives into episodes, alarms and an audit.
"""
        ),
    ]
    return save("tutorial_business_intermediate.ipynb", cells)


# ---------------------------------------------------------------------------
# Advanced
# ---------------------------------------------------------------------------


def build_advanced() -> str:
    cells = [
        md(INTRO),
        code(BOOTSTRAP),
        md(
            """\
# Advanced — episodes, alarms, audits

Two of the next three lessons are the reason window functions are worth a raise:

* **A1** turns thousands of noisy ticks into a handful of *episodes* (the
  **gap-and-islands** pattern).
* **A2** turns an alert stream into *alarm events* with a quiet-period rule
  (**sessionization**).
* **A3** audits the monitor itself: observed telemetry vs the *true* physiology
  table, minute by minute.

### A1 — "How many DISTINCT desaturation episodes did Naomi have?"

Naomi spent over an hour below 94% — but "below 94%" is not one event. The
trace dips, recovers, dips again. A clinical reviewer wants each **distinct
episode**: start, end, duration, lowest and average SpO2.

*What this teaches:* gap-and-islands in four moves — (1) flag each reading, (2)
`LAG()` detects where the flag *transitions* 0 → 1, (3) a running `SUM()` of
those transitions gives every contiguous bad stretch a shared bucket number
(the *island*), (4) `GROUP BY` the island and summarize.
"""
        ),
        *lesson_block("a1_desaturation_episodes"),
        md(
            """\
**Reading the result.** 25 "episodes"?! With the device's noise, the raw trace
re-crosses the 94% line constantly at the shoulders of the plateau — so a naive
island detector shatters one clinical event into fragments. Two honest
takeaways:

* The **fragmentation is information**: it tells you the monitor is noisy and
  the patient is sitting right at the threshold.
* A real analyst lowers the threshold, smooths first (I2), or adds a *healing*
  rule — gaps under a minute get merged. Watch A2 encode that quiet-period rule.

See the episodes on a timeline:
"""
        ),
        code(
            """\
episodes = run_lesson(lesson("a1_desaturation_episodes")).copy()
episodes["start"] = tz_free(episodes["episode_start"])
episodes["end"] = tz_free(episodes["episode_end"])
episodes = episodes.sort_values("start").reset_index(drop=True)

fig, ax = plt.subplots(figsize=(11, 5))
for i in range(len(episodes)):
    minutes = (episodes["end"].iloc[i] - episodes["start"].iloc[i]).total_seconds() / 60
    ax.barh(i, minutes, left=episodes["start"].iloc[i], height=0.8,
            color="#d62728", alpha=0.6)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.set_xlabel("time")
ax.set_ylabel(f"episode idx ({len(episodes)} total)")
ax.set_title("Below-94% episodes - device noise fragments the main event")
ax.set_xlim(pd.Timestamp("2026-01-01 02:00:00"), pd.Timestamp("2026-01-01 05:00:00"))
plt.tight_layout()
plt.show()
"""
        ),
        code(
            """\
a1_90 = load_lesson_sql(lesson("a1_desaturation_episodes")).replace("spo2_pct < 94", "spo2_pct < 90")
deep = run_live(a1_90)
print(f"threshold 90% -> {len(deep)} episodes, "
      f"{int(deep['readings'].sum())} low readings")
display(deep.head(10))
"""
        ),
        md(
            """\
**Try it.** That cell re-ran the SAME query with a **90% threshold** by
splicing the lesson text. With the deeper threshold the trace still fragments,
but far less — the crossing region is smaller. Episode counts must always be
reported *together with the threshold that produced them*.

### A2 — "Turn hundreds of alarm ticks into 2 alarm events"

An alarm that rings below 90% SpO2 fires nearly every 5 seconds during Naomi's
desaturation — useless for a tired clinician. Rule: collapse a continuous burst
into ONE event, and start a NEW event only after **2 minutes of quiet**. How
many real alarms fired, and what did each cover?

*What this teaches:* **sessionization** — filter to the hits, measure the gap to
the previous hit with `LAG()`, then a running `SUM()` that seeds a new session
whenever the gap >= 120 seconds.
"""
        ),
        *lesson_block("a2_alarm_sessions"),
        md(
            """\
**Reading the result.** Two alarms fired that night:

1. **02:54:40** — a *single* reading at 89%. One tick, then nothing for 2+
   minutes. Almost certainly the sensor spike / onset blip.
2. **02:56:45 → 04:05:45** — the *real* event: 786 readings, lowest 87,
   average 88.9.

The burst of raw alarm ticks became **one** reportable alarm event.
"""
        ),
        code(
            """\
sessions = run_lesson(lesson("a2_alarm_sessions")).copy()
starts = tz_free(sessions["alarm_started"])
ends = tz_free(sessions["alarm_ended"])

trace = run_live(
    "SELECT event_time, spo2_pct FROM lake.lakehouse.vitals "
    f"WHERE patient_id = '{NAOMI}' ORDER BY event_time"
)
trace["t"] = tz_free(trace["event_time"])
minute = trace.set_index("t")["spo2_pct"].resample("1min").median()

fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(minute.index, minute.values, color="#7f7f7f", lw=1.2)
for i in range(len(sessions)):
    ax.axvspan(starts.iloc[i], ends.iloc[i], color="#d62728", alpha=0.35)
ax.axhline(90, color="#ff7f0e", ls="--", lw=1.2)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.set_xlabel("time")
ax.set_ylabel("minute-median SpO2 (%)")
ax.set_title("Alarm sessionization - one red band per REPORTED alarm event")
plt.tight_layout()
plt.show()
"""
        ),
        md(
            """\
**Reading this chart.** Each red band is one alarm *event* — the whole
desaturation — while "how many readings were low?" would have screamed
*hundreds*. The grey trace between bands is the "quiet" a sessionizer required
before starting a new session.

### A3 — "Can we trust the monitor? Audit device readings vs the truth"

The bedside monitor is an instrument (Milestone 8): it adds noise, rounds
values, occasionally drops a reading. We seeded `lake.lakehouse.vitals_truth` —
the *exact* simulated physiology for every tick — precisely so fidelity can be
MEASURED. How far is observed telemetry from true physiology, minute by minute?

*What this teaches:* resampling with `date_trunc('minute', ...)` + **median**
(robust to the spikes a mean would drag around), a clean cross-table JOIN on
shared `(minute, patient)` buckets, and a grouped aggregate computing **bias**
(mean signed error) and **MAE** (mean absolute error).
"""
        ),
        *lesson_block("a3_observed_vs_truth"),
        md(
            """\
**Reading the result.** One row per minute for Naomi's stay, with observed
minute-median, true minute-median and the error. Overall the bias ≈ 0 (the
monitor is not systematically lying) but per-minute errors are non-zero,
driven by the dropout windows and the sensor spikes. The grand bottom line:
"""
        ),
        code(
            """\
audit = run_lesson(lesson("a3_observed_vs_truth")).copy()
audit["t"] = tz_free(audit["minute_bucket"])

fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
ax_top.plot(audit["t"], audit["true_spo2"], color="#1f77b4", lw=1.6, label="true")
ax_top.plot(audit["t"], audit["observed_spo2"], color="#d62728", lw=1.2,
            alpha=0.8, label="observed")
ax_top.set_ylabel("SpO2 (%)")
ax_top.set_title("Naomi - true physiology vs the bedside monitor's readings")
ax_top.legend(loc="lower right", ncol=2)

ax_bot.plot(audit["t"], audit["abs_error"], color="grey", lw=0.9)
ax_bot.set_ylabel("|obs - truth|")
ax_bot.set_xlabel("time")
ax_bot.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
plt.tight_layout()
plt.show()

stats = audit["abs_error"].describe()
print(f"MAE over {len(audit)} minutes: {stats['mean']:.3f} points "
      f"(worst minute: {stats['max']:.3f})")
"""
        ),
        md(
            """\
**What you now know.** You went from "who is on the ward?" (a JOIN) to
"audit a sensor against ground truth" (a cross-catalog, resampled,
window-tolerant join). The full arc of the series:

* `SELECT`/`JOIN`/`ORDER BY` — *shape* the data
* `date_trunc` + `GROUP BY` — *bucket* the data
* CTEs — *compose* the query
* `LAG`/`LEAD` — *before / after*
* moving averages — *sustained trends*
* `RANK`/`NTILE` — *rank & distribution*
* gap-and-islands — *episodes*
* sessionization — *events from streams*

**Final exercises** (in `sql/dql/advanced/`):

1. `a1_desaturation_episodes.sql` — add a heal rule: only start a new island
   when the gap to the previous island is >= 60 s. (Hint: `LAG()` on the
   island-start rows, then the classic running `SUM`.)
2. `a2_alarm_sessions.sql` — change the quiet window from `120` to `30`
   seconds. The two alarms become three or more: shorter quiet → more
   fragments. That is the cost/benefit knob of every paging policy.
3. `a3_observed_vs_truth.sql` — switch to Cole's patient id. Which channel
   really needs the audit?
"""
        ),
    ]
    return save("tutorial_business_advanced.ipynb", cells)


if __name__ == "__main__":
    for name in (build_beginner(), build_intermediate(), build_advanced()):
        print(f"built notebooks/{name}")