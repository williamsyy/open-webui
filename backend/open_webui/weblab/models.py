"""Schema for the Web Lab study database.

The study is hierarchical:

    case_study            one A/B study ("Fall 2026 high-demand postponement")
      └── participant     a user enrolled in it — enrolment is what starts
                          data collection for that user, independent of which
                          arm they are in.  A user may be a participant in
                          several case studies over different periods.
            └── membership   which arm (control / treatment) the participant is
                             in, as an append-only history.  Moving a user from
                             control to treatment in week 2 closes the current
                             row and opens a new one; nothing is overwritten,
                             so any past moment can be reconstructed exactly.

Around that sit the observations: ``usage_record`` (token usage mirrored out of
Open WebUI as it happens), ``demand_window`` (the high-demand periods loaded
from CSV), ``intervention`` (a popup shown and what the user clicked) and
``postponement`` (the resulting hold).  ``study_event`` is a catch-all
append-only audit log.

Nothing in this file is ever updated destructively except where a row has an
explicit lifecycle (``effective_to``, ``status``, ``decision``), so the study
can be replayed from the database alone.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from open_webui.internal.db import JSONField
from open_webui.weblab.db import WeblabBase
from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Index, Integer, String, Text


def new_id() -> str:
    return str(uuid.uuid4())


def now_ts() -> int:
    return int(time.time())


####################
# Tables
####################


class CaseStudy(WeblabBase):
    """One A/B study.  Several may run at once over different populations."""

    __tablename__ = 'weblab_case_study'

    id = Column(String(64), primary_key=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # draft → running → completed → archived
    status = Column(String(32), nullable=False, default='draft')

    # IANA name; every wall-clock value entered for this study is read in it.
    timezone = Column(String(64), nullable=False, default='America/New_York')

    # Overall observation window.  Usage is collected for participants from the
    # moment they are enrolled; these bound the study as a whole.
    starts_at = Column(BigInteger, nullable=True)
    ends_at = Column(BigInteger, nullable=True)

    # When the treatment arm actually starts seeing popups.  Before this, the
    # study is observation-only for everybody (the week-1 baseline).
    intervention_starts_at = Column(BigInteger, nullable=True)
    intervention_ends_at = Column(BigInteger, nullable=True)

    # How the end of a postponement is decided:
    #   'fixed'      – always postpone_minutes from acceptance
    #   'window_end' – until the current high-demand window closes
    postpone_mode = Column(String(32), nullable=False, default='fixed')
    postpone_minutes = Column(Float, nullable=False, default=5.0)
    # Guard rails for 'window_end' so a window closing in 10 seconds (or in
    # four hours) does not produce a useless or punitive hold.
    postpone_min_minutes = Column(Float, nullable=False, default=1.0)
    postpone_max_minutes = Column(Float, nullable=True)

    # Do not re-ask the same user within this many minutes of a popup.
    reprompt_cooldown_minutes = Column(Float, nullable=False, default=10.0)
    # Only ask inside a loaded high-demand window (the normal case).  When
    # false the arm is asked on every eligible message.
    require_demand_window = Column(Boolean, nullable=False, default=True)
    # Fraction of eligible messages that trigger a popup (1.0 = always).
    trigger_probability = Column(Float, nullable=False, default=1.0)
    # Let the user send anyway while a postponement is running.
    allow_override = Column(Boolean, nullable=False, default=True)

    # Popup copy, editable per study.
    prompt_title = Column(Text, nullable=True)
    prompt_body = Column(Text, nullable=True)
    accept_label = Column(Text, nullable=True)
    decline_label = Column(Text, nullable=True)
    waiting_body = Column(Text, nullable=True)

    created_by = Column(String(64), nullable=True)
    created_at = Column(BigInteger, nullable=False, default=now_ts)
    updated_at = Column(BigInteger, nullable=False, default=now_ts)


class StudyGroup(WeblabBase):
    """An arm of a case study."""

    __tablename__ = 'weblab_group'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(Text, nullable=False)
    kind = Column(String(32), nullable=False)  # 'control' | 'treatment'
    description = Column(Text, nullable=True)
    created_at = Column(BigInteger, nullable=False, default=now_ts)


class Participant(WeblabBase):
    """A user enrolled in a case study — the global level.

    Enrolment is deliberately separate from arm membership: a user is *in the
    study* (and therefore has their usage collected) from ``joined_at``, even
    during week 1 when no one is in treatment yet.
    """

    __tablename__ = 'weblab_participant'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)

    # Denormalised so the study file remains meaningful without webui.db.
    user_email = Column(Text, nullable=True)
    user_name = Column(Text, nullable=True)

    joined_at = Column(BigInteger, nullable=False, default=now_ts)
    left_at = Column(BigInteger, nullable=True)
    status = Column(String(32), nullable=False, default='active')  # active | ended

    note = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(BigInteger, nullable=False, default=now_ts)


Index('ix_weblab_participant_study_user', Participant.case_study_id, Participant.user_id)


class Membership(WeblabBase):
    """Append-only record of which arm a participant was in, and when.

    The current arm is the row with ``effective_to IS NULL``.  Reassigning a
    user stamps ``effective_to`` on that row and inserts a new one, so the arm
    in force at any past timestamp is always recoverable.
    """

    __tablename__ = 'weblab_membership'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    participant_id = Column(String(64), ForeignKey('weblab_participant.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)

    group_id = Column(String(64), ForeignKey('weblab_group.id', ondelete='CASCADE'), nullable=False, index=True)
    kind = Column(String(32), nullable=False)  # denormalised 'control' | 'treatment'

    effective_from = Column(BigInteger, nullable=False, default=now_ts)
    effective_to = Column(BigInteger, nullable=True)

    reason = Column(Text, nullable=True)
    changed_by = Column(String(64), nullable=True)
    created_at = Column(BigInteger, nullable=False, default=now_ts)


Index('ix_weblab_membership_current', Membership.user_id, Membership.case_study_id, Membership.effective_to)


class DemandWindowImport(WeblabBase):
    """One CSV upload of high-demand windows, kept verbatim for provenance."""

    __tablename__ = 'weblab_demand_import'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    filename = Column(Text, nullable=True)
    timezone = Column(String(64), nullable=True)
    row_count = Column(Integer, nullable=False, default=0)
    skipped_count = Column(Integer, nullable=False, default=0)
    replaced = Column(Boolean, nullable=False, default=False)
    raw_csv = Column(Text, nullable=True)
    warnings = Column(JSONField, nullable=True)
    imported_by = Column(String(64), nullable=True)
    imported_at = Column(BigInteger, nullable=False, default=now_ts)


class DemandWindow(WeblabBase):
    """A period during which the system is declared to be in high demand."""

    __tablename__ = 'weblab_demand_window'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    import_id = Column(String(64), ForeignKey('weblab_demand_import.id', ondelete='SET NULL'), nullable=True, index=True)

    starts_at = Column(BigInteger, nullable=False, index=True)
    ends_at = Column(BigInteger, nullable=False, index=True)

    # Exactly what the CSV said, kept for auditing alongside the epoch values.
    local_start = Column(Text, nullable=True)
    local_end = Column(Text, nullable=True)
    timezone = Column(String(64), nullable=True)

    label = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, default='csv')  # csv | manual
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(64), nullable=True)
    created_at = Column(BigInteger, nullable=False, default=now_ts)


class UsageRecord(WeblabBase):
    """Token usage for one assistant message, mirrored as it is written.

    This is what makes the study file self-contained: the usage history does
    not depend on ``chat_message`` in webui.db still existing.
    """

    __tablename__ = 'weblab_usage_record'

    id = Column(String(128), primary_key=True)  # {chat_id}-{message_id}
    user_id = Column(String(64), nullable=False, index=True)
    chat_id = Column(String(64), nullable=True, index=True)
    message_id = Column(String(64), nullable=True)
    model_id = Column(Text, nullable=True)

    input_tokens = Column(BigInteger, nullable=False, default=0)
    output_tokens = Column(BigInteger, nullable=False, default=0)
    total_tokens = Column(BigInteger, nullable=False, default=0)

    # Message timestamp (when the exchange happened) and mirror timestamp.
    created_at = Column(BigInteger, nullable=False, index=True)
    recorded_at = Column(BigInteger, nullable=False, default=now_ts)
    raw_usage = Column(JSONField, nullable=True)


class MessageRecord(WeblabBase):
    """One user prompt, counted even when the model reports no usage.

    Message volume is a study measure in its own right, and some providers
    return no token accounting at all.
    """

    __tablename__ = 'weblab_message_record'

    id = Column(String(128), primary_key=True)  # {chat_id}-{message_id}
    user_id = Column(String(64), nullable=False, index=True)
    chat_id = Column(String(64), nullable=True, index=True)
    message_id = Column(String(64), nullable=True)
    model_id = Column(Text, nullable=True)
    role = Column(String(32), nullable=False, default='user')
    created_at = Column(BigInteger, nullable=False, index=True)
    recorded_at = Column(BigInteger, nullable=False, default=now_ts)


class Intervention(WeblabBase):
    """A high-demand popup shown to a participant, and what they did with it."""

    __tablename__ = 'weblab_intervention'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    participant_id = Column(String(64), ForeignKey('weblab_participant.id', ondelete='CASCADE'), nullable=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)

    group_id = Column(String(64), nullable=True)
    group_kind = Column(String(32), nullable=True)
    # The membership row in force when the popup fired — so a later arm change
    # never rewrites the history of what this user was shown.
    membership_id = Column(String(64), nullable=True)

    demand_window_id = Column(String(64), ForeignKey('weblab_demand_window.id', ondelete='SET NULL'), nullable=True, index=True)
    demand_window_label = Column(Text, nullable=True)
    demand_window_ends_at = Column(BigInteger, nullable=True)

    chat_id = Column(String(64), nullable=True)

    shown_at = Column(BigInteger, nullable=False, default=now_ts, index=True)
    decision = Column(String(32), nullable=False, default='pending')  # pending|accepted|declined|dismissed|expired
    decided_at = Column(BigInteger, nullable=True)
    # Seconds between the popup appearing and the click — a study measure.
    response_seconds = Column(Float, nullable=True)

    offered_mode = Column(String(32), nullable=True)  # fixed | window_end
    offered_seconds = Column(Integer, nullable=True)
    prompt_text = Column(Text, nullable=True)
    client_meta = Column(JSONField, nullable=True)


class Postponement(WeblabBase):
    """A hold a participant accepted."""

    __tablename__ = 'weblab_postponement'

    id = Column(String(64), primary_key=True)
    intervention_id = Column(String(64), ForeignKey('weblab_intervention.id', ondelete='CASCADE'), nullable=True, index=True)
    case_study_id = Column(String(64), ForeignKey('weblab_case_study.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)

    started_at = Column(BigInteger, nullable=False, default=now_ts)
    ends_at = Column(BigInteger, nullable=False)
    mode = Column(String(32), nullable=False, default='fixed')

    status = Column(String(32), nullable=False, default='active')  # active|completed|overridden|cancelled
    released_at = Column(BigInteger, nullable=True)
    release_reason = Column(Text, nullable=True)
    # Did the user actually wait it out?
    honoured = Column(Boolean, nullable=True)


class StudyEvent(WeblabBase):
    """Append-only log of everything else worth keeping (admin actions included)."""

    __tablename__ = 'weblab_event'

    id = Column(String(64), primary_key=True)
    case_study_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(64), nullable=True, index=True)
    actor_id = Column(String(64), nullable=True)
    type = Column(String(64), nullable=False, index=True)
    data = Column(JSONField, nullable=True)
    created_at = Column(BigInteger, nullable=False, default=now_ts, index=True)


####################
# Pydantic models
####################


class CaseStudyModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str] = None
    status: str
    timezone: str
    starts_at: Optional[int] = None
    ends_at: Optional[int] = None
    intervention_starts_at: Optional[int] = None
    intervention_ends_at: Optional[int] = None
    postpone_mode: str
    postpone_minutes: float
    postpone_min_minutes: float
    postpone_max_minutes: Optional[float] = None
    reprompt_cooldown_minutes: float
    require_demand_window: bool
    trigger_probability: float
    allow_override: bool
    prompt_title: Optional[str] = None
    prompt_body: Optional[str] = None
    accept_label: Optional[str] = None
    decline_label: Optional[str] = None
    waiting_body: Optional[str] = None
    created_by: Optional[str] = None
    created_at: int
    updated_at: int


class StudyGroupModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_study_id: str
    name: str
    kind: str
    description: Optional[str] = None
    created_at: int


class ParticipantModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_study_id: str
    user_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    joined_at: int
    left_at: Optional[int] = None
    status: str
    note: Optional[str] = None
    created_by: Optional[str] = None
    created_at: int


class MembershipModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_study_id: str
    participant_id: str
    user_id: str
    group_id: str
    kind: str
    effective_from: int
    effective_to: Optional[int] = None
    reason: Optional[str] = None
    changed_by: Optional[str] = None
    created_at: int


class DemandWindowModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_study_id: str
    import_id: Optional[str] = None
    starts_at: int
    ends_at: int
    local_start: Optional[str] = None
    local_end: Optional[str] = None
    timezone: Optional[str] = None
    label: Optional[str] = None
    source: str
    active: bool
    created_at: int


class InterventionModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_study_id: str
    user_id: str
    group_kind: Optional[str] = None
    demand_window_id: Optional[str] = None
    demand_window_label: Optional[str] = None
    chat_id: Optional[str] = None
    shown_at: int
    decision: str
    decided_at: Optional[int] = None
    response_seconds: Optional[float] = None
    offered_mode: Optional[str] = None
    offered_seconds: Optional[int] = None


class PostponementModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_study_id: str
    user_id: str
    intervention_id: Optional[str] = None
    started_at: int
    ends_at: int
    mode: str
    status: str
    released_at: Optional[int] = None
    release_reason: Optional[str] = None
    honoured: Optional[bool] = None


class InterventionCheckResponse(BaseModel):
    """What the chat client is told before a message is sent."""

    action: str = 'none'  # none | prompt | waiting
    case_study_id: Optional[str] = None
    case_study_name: Optional[str] = None
    intervention_id: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    accept_label: Optional[str] = None
    decline_label: Optional[str] = None
    postpone_seconds: Optional[int] = None
    postpone_mode: Optional[str] = None
    ends_at: Optional[int] = None
    remaining_seconds: Optional[int] = None
    allow_override: bool = True
    demand_window_label: Optional[str] = None
    debug: Optional[dict[str, Any]] = None
