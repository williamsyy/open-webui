# Web Lab

Chatbot usage monitoring and high-demand postponement studies, built into this
Open WebUI deployment. Admin UI: **Admin → Web Lab** (`/admin/weblab`).

## The study database

All study data lives in its own SQLite file, separate from Open WebUI's
`webui.db`:

    /opt/open-webui/data/weblab.db

That separation is the point: the study survives an Open WebUI upgrade, a
migration, or a reset of the main database. Token usage is **mirrored** into it
as messages are written rather than referenced, so the study stays complete
even if chat history is later deleted.

Override with environment variables in `openwebui.env`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `WEBLAB_DB_PATH` | `$DATA_DIR/weblab.db` | The study database file |
| `WEBLAB_DATABASE_URL` | derived from the above | Full SQLAlchemy URL |
| `WEBLAB_BACKUP_DIR` | `$DATA_DIR/weblab-backups` | Where snapshots go |
| `WEBLAB_BACKUP_INTERVAL_SECONDS` | `86400` | Automatic snapshot interval |
| `WEBLAB_BACKUP_RETENTION` | `30` | How many snapshots to keep |

### Tables

| Table | Holds |
| --- | --- |
| `weblab_case_study` | One A/B study: phases, timezone, postponement rules, popup copy |
| `weblab_group` | Its arms (control / treatment) |
| `weblab_participant` | Global enrolment — the moment a user's data starts being collected |
| `weblab_membership` | **Append-only** history of which arm each participant was in, and when |
| `weblab_demand_window` | High-demand periods, loaded from CSV or added by hand |
| `weblab_demand_import` | Each CSV upload, kept verbatim with its warnings |
| `weblab_usage_record` | Token usage per assistant message, mirrored from the chat |
| `weblab_message_record` | One row per user prompt (volume, even when a provider reports no tokens) |
| `weblab_intervention` | Every popup shown, and what the user clicked |
| `weblab_postponement` | Every accepted hold, and whether it was waited out |
| `weblab_event` | Append-only audit log, admin actions included |

Enrolment and arm membership are deliberately separate. A user is *in the
study* — and being measured — from the day they are enrolled, whatever arm they
are in. Moving someone from control to treatment in week 2 closes their current
membership row and opens a new one; nothing is overwritten, so the arm in force
at any past timestamp is always recoverable.

## Backup and recovery

Snapshots are written on startup and every `WEBLAB_BACKUP_INTERVAL_SECONDS`
(default: daily) using SQLite `VACUUM INTO`, which is consistent while the app
keeps writing. Each snapshot is a complete, openable database.

From **Admin → Web Lab → Data** you can take a snapshot, verify one's
integrity, restore from one, or download the whole database.

Restoring from the command line:

    systemctl stop open-webui
    cp /opt/open-webui/data/weblab-backups/weblab-YYYYMMDD-HHMMSS.db \
       /opt/open-webui/data/weblab.db
    rm -f /opt/open-webui/data/weblab.db-wal /opt/open-webui/data/weblab.db-shm
    systemctl start open-webui

Restoring through the UI snapshots the current database first, so a restore is
never a one-way door. Either way, restart the service afterwards so it reopens
the restored file.

To pull the study onto another machine for analysis, just copy `weblab.db` —
it needs nothing else.

## Running a study

1. **Create a case study** (Case studies → New). Set the study period, and set
   *Treatment starts* to the beginning of week 2. Choose how long a
   postponement lasts:
   - **A fixed amount of time** — every accepted postponement is the same
     length.
   - **Until the high-demand window ends** — the wait runs to the close of
     whichever window is in force, clamped by a floor and an optional ceiling.
     If no window happens to be open, the fixed time is used instead.
2. **Enrol users** (Participants → Enrol users). Everyone starts in control and
   their usage begins being recorded immediately — that is week 1.
3. **Load demand windows** (Demand windows). Upload a CSV:

       start,end,label
       2026-09-07 09:00,2026-09-07 11:00,Monday morning peak
       2026-09-07 14:00,2026-09-07 16:30,Monday afternoon peak

   Times are read in the case study's timezone unless a row carries its own UTC
   offset or the file has a `timezone` column. `start`/`end` also accept ISO
   8601, `MM/DD/YYYY h:mm AM`, and epoch seconds. Bad rows are skipped with a
   warning rather than failing the upload, and the file is previewed before
   anything is written.
4. **Week 2: move people to treatment** — select participants and press
   *→ Treatment* (or *Randomise arms*). You are asked for a reason, which is
   stored with the change.
5. **Set the case study to Running.** Popups now fire for treatment
   participants inside a loaded demand window, once the treatment period opens.
6. **Watch it** in Usage (token distribution, per-user table, hour-of-day
   profile) and Results (arm comparison, acceptance rate, per-window
   acceptance, audit log). Export as CSV or JSON at any time.

Several case studies can run at once, and a user may be a participant in more
than one over different periods.

## How the popup behaves

Checked just before a message is sent. A study can only ever *delay* a message,
never lose one: declining, dismissing, an override, or any error sends it
straight through. Accepting holds the message and sends it automatically when
the timer ends.

To see why you would or would not get a popup right now, as an admin:

    GET /api/v1/weblab/debug

It returns the per-study trace — arm, phase, demand window, cooldown, and the
reason for each skip.
