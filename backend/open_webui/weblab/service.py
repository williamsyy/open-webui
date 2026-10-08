"""Study logic: enrolment, arm history, demand windows, interventions, analytics.

Every write here is designed to be additive.  Reassigning a user closes one
membership row and opens another; a decision stamps the intervention it belongs
to; usage is mirrored rather than referenced.  The result is that the study
database alone answers "what was true for this user at this moment", which is
what an A/B analysis needs months later.
"""

from __future__ import annotations

import json
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from open_webui.weblab.db import get_weblab_db
from open_webui.weblab.demand_csv import parse_demand_csv
from open_webui.weblab.models import (
    CaseStudy,
    DemandWindow,
    DemandWindowImport,
    Intervention,
    InterventionCheckResponse,
    Membership,
    MessageRecord,
    Participant,
    Postponement,
    StudyEvent,
    StudyGroup,
    UsageRecord,
    new_id,
    now_ts,
)
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

DEFAULT_PROMPT_TITLE = 'The system is in high demand'
DEFAULT_PROMPT_BODY = (
    'We are seeing unusually heavy usage right now. Are you happy to postpone '
    'this response for a few minutes? Your message will be sent automatically '
    'when the wait is over.'
)
DEFAULT_ACCEPT_LABEL = 'Yes, postpone my response'
DEFAULT_DECLINE_LABEL = 'No, send it now'
DEFAULT_WAITING_BODY = 'Thanks for waiting — your message will go through when the timer ends.'


async def log_event(
    db: AsyncSession,
    type: str,
    *,
    case_study_id: Optional[str] = None,
    user_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    data: Optional[dict] = None,
) -> None:
    """Append to the study audit log.  Caller commits."""
    db.add(
        StudyEvent(
            id=new_id(),
            case_study_id=case_study_id,
            user_id=user_id,
            actor_id=actor_id,
            type=type,
            data=data,
            created_at=now_ts(),
        )
    )


####################
# Case studies & groups
####################


async def list_case_studies(db: Optional[AsyncSession] = None) -> list[dict]:
    async with get_weblab_db(db) as db:
        studies = (await db.execute(select(CaseStudy).order_by(CaseStudy.created_at.desc()))).scalars().all()
        out = []
        for study in studies:
            participants = (
                await db.execute(
                    select(func.count()).select_from(Participant).where(
                        Participant.case_study_id == study.id, Participant.status == 'active'
                    )
                )
            ).scalar() or 0
            windows = (
                await db.execute(
                    select(func.count()).select_from(DemandWindow).where(
                        DemandWindow.case_study_id == study.id, DemandWindow.active.is_(True)
                    )
                )
            ).scalar() or 0
            out.append(
                {
                    **_study_dict(study),
                    'participant_count': participants,
                    'demand_window_count': windows,
                    'phase': current_phase(study),
                }
            )
        return out


def _study_dict(study: CaseStudy) -> dict:
    return {
        c.name: getattr(study, c.name) for c in study.__table__.columns
    }


def current_phase(study: CaseStudy, now: Optional[int] = None) -> str:
    """Which part of its life the study is in right now."""
    now = now or now_ts()
    if study.status in ('draft', 'archived'):
        return study.status
    if study.starts_at and now < study.starts_at:
        return 'scheduled'
    if study.ends_at and now > study.ends_at:
        return 'ended'
    if study.intervention_starts_at and now < study.intervention_starts_at:
        return 'baseline'
    if study.intervention_ends_at and now > study.intervention_ends_at:
        return 'post-treatment'
    if study.intervention_starts_at:
        return 'treatment'
    return 'observation'


async def create_case_study(payload: dict, actor_id: Optional[str], db: Optional[AsyncSession] = None) -> dict:
    async with get_weblab_db(db) as db:
        study = CaseStudy(
            id=new_id(),
            name=payload.get('name') or 'Untitled case study',
            description=payload.get('description'),
            status=payload.get('status') or 'draft',
            timezone=payload.get('timezone') or 'America/New_York',
            starts_at=payload.get('starts_at'),
            ends_at=payload.get('ends_at'),
            intervention_starts_at=payload.get('intervention_starts_at'),
            intervention_ends_at=payload.get('intervention_ends_at'),
            postpone_mode=payload.get('postpone_mode') or 'fixed',
            postpone_minutes=payload.get('postpone_minutes', 5.0),
            postpone_min_minutes=payload.get('postpone_min_minutes', 1.0),
            postpone_max_minutes=payload.get('postpone_max_minutes'),
            reprompt_cooldown_minutes=payload.get('reprompt_cooldown_minutes', 10.0),
            require_demand_window=payload.get('require_demand_window', True),
            trigger_probability=payload.get('trigger_probability', 1.0),
            allow_override=payload.get('allow_override', True),
            prompt_title=payload.get('prompt_title') or DEFAULT_PROMPT_TITLE,
            prompt_body=payload.get('prompt_body') or DEFAULT_PROMPT_BODY,
            accept_label=payload.get('accept_label') or DEFAULT_ACCEPT_LABEL,
            decline_label=payload.get('decline_label') or DEFAULT_DECLINE_LABEL,
            waiting_body=payload.get('waiting_body') or DEFAULT_WAITING_BODY,
            created_by=actor_id,
            created_at=now_ts(),
            updated_at=now_ts(),
        )
        db.add(study)

        # Every study gets the two standard arms up front; users start in
        # control and are moved to treatment when the study calls for it.
        for kind, name in (('control', 'Control'), ('treatment', 'Treatment')):
            db.add(
                StudyGroup(
                    id=new_id(),
                    case_study_id=study.id,
                    name=name,
                    kind=kind,
                    created_at=now_ts(),
                )
            )

        await log_event(db, 'case_study.created', case_study_id=study.id, actor_id=actor_id, data={'name': study.name})
        await db.commit()
        return _study_dict(study)


async def update_case_study(
    case_study_id: str, payload: dict, actor_id: Optional[str], db: Optional[AsyncSession] = None
) -> Optional[dict]:
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            return None
        changed = {}
        editable = {c.name for c in CaseStudy.__table__.columns} - {'id', 'created_at', 'created_by'}
        for key, value in payload.items():
            if key in editable and getattr(study, key) != value:
                changed[key] = {'from': getattr(study, key), 'to': value}
                setattr(study, key, value)
        study.updated_at = now_ts()
        if changed:
            await log_event(db, 'case_study.updated', case_study_id=study.id, actor_id=actor_id, data=changed)
        await db.commit()
        return _study_dict(study)


async def delete_case_study(case_study_id: str, actor_id: Optional[str], db: Optional[AsyncSession] = None) -> bool:
    """Archive rather than delete — study data is never thrown away here."""
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            return False
        study.status = 'archived'
        study.updated_at = now_ts()
        await log_event(db, 'case_study.archived', case_study_id=case_study_id, actor_id=actor_id)
        await db.commit()
        return True


async def get_groups(case_study_id: str, db: Optional[AsyncSession] = None) -> list[StudyGroup]:
    async with get_weblab_db(db) as db:
        return list(
            (
                await db.execute(
                    select(StudyGroup).where(StudyGroup.case_study_id == case_study_id).order_by(StudyGroup.kind)
                )
            )
            .scalars()
            .all()
        )


####################
# Participants & arm membership
####################


async def enroll_participants(
    case_study_id: str,
    users: list[dict],
    actor_id: Optional[str],
    *,
    group_kind: str = 'control',
    joined_at: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> dict:
    """Enrol users into the study (the global level) and open a membership row.

    Re-enrolling someone who left reopens their participation; already-active
    participants are left alone.
    """
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            return {'enrolled': 0, 'reactivated': 0, 'skipped': 0}

        groups = {g.kind: g for g in (await get_groups(case_study_id, db))}
        group = groups.get(group_kind) or groups.get('control')
        if group is None:
            group = StudyGroup(
                id=new_id(), case_study_id=case_study_id, name=group_kind.title(), kind=group_kind, created_at=now_ts()
            )
            db.add(group)
            await db.flush()

        stamp = joined_at or now_ts()
        enrolled = reactivated = skipped = 0

        for user in users:
            user_id = user.get('id') or user.get('user_id')
            if not user_id:
                continue

            existing = (
                await db.execute(
                    select(Participant).where(
                        Participant.case_study_id == case_study_id, Participant.user_id == user_id
                    )
                )
            ).scalars().first()

            if existing and existing.status == 'active':
                skipped += 1
                continue

            if existing:
                existing.status = 'active'
                existing.left_at = None
                participant = existing
                reactivated += 1
            else:
                participant = Participant(
                    id=new_id(),
                    case_study_id=case_study_id,
                    user_id=user_id,
                    user_email=user.get('email'),
                    user_name=user.get('name'),
                    joined_at=stamp,
                    status='active',
                    created_by=actor_id,
                    created_at=now_ts(),
                )
                db.add(participant)
                await db.flush()
                enrolled += 1

            await _open_membership(db, study, participant, group, actor_id, reason='enrolled', at=stamp)
            await log_event(
                db,
                'participant.enrolled',
                case_study_id=case_study_id,
                user_id=user_id,
                actor_id=actor_id,
                data={'group': group.kind, 'joined_at': stamp},
            )

        await db.commit()
        return {'enrolled': enrolled, 'reactivated': reactivated, 'skipped': skipped}


async def _open_membership(
    db: AsyncSession,
    study: CaseStudy,
    participant: Participant,
    group: StudyGroup,
    actor_id: Optional[str],
    *,
    reason: Optional[str] = None,
    at: Optional[int] = None,
) -> Membership:
    """Close any open membership and open a new one.  Caller commits."""
    stamp = at or now_ts()

    open_rows = (
        await db.execute(
            select(Membership).where(
                Membership.participant_id == participant.id, Membership.effective_to.is_(None)
            )
        )
    ).scalars().all()

    for row in open_rows:
        if row.group_id == group.id:
            return row  # already in this arm — nothing to record
        row.effective_to = stamp

    membership = Membership(
        id=new_id(),
        case_study_id=study.id,
        participant_id=participant.id,
        user_id=participant.user_id,
        group_id=group.id,
        kind=group.kind,
        effective_from=stamp,
        reason=reason,
        changed_by=actor_id,
        created_at=now_ts(),
    )
    db.add(membership)
    await db.flush()
    return membership


async def set_membership(
    case_study_id: str,
    user_ids: list[str],
    group_kind: str,
    actor_id: Optional[str],
    *,
    reason: Optional[str] = None,
    effective_at: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> dict:
    """Move participants into an arm, preserving the previous membership row."""
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            return {'moved': 0}

        groups = {g.kind: g for g in (await get_groups(case_study_id, db))}
        group = groups.get(group_kind)
        if group is None:
            return {'moved': 0, 'error': f'No "{group_kind}" group in this case study.'}

        moved = 0
        for user_id in user_ids:
            participant = (
                await db.execute(
                    select(Participant).where(
                        Participant.case_study_id == case_study_id, Participant.user_id == user_id
                    )
                )
            ).scalars().first()
            if not participant:
                continue
            previous = await get_current_membership(case_study_id, user_id, db=db)
            membership = await _open_membership(
                db, study, participant, group, actor_id, reason=reason or 'reassigned', at=effective_at
            )
            if previous is None or previous.id != membership.id:
                moved += 1
                await log_event(
                    db,
                    'membership.changed',
                    case_study_id=case_study_id,
                    user_id=user_id,
                    actor_id=actor_id,
                    data={
                        'from': previous.kind if previous else None,
                        'to': group.kind,
                        'reason': reason,
                        'effective_at': membership.effective_from,
                    },
                )
        await db.commit()
        return {'moved': moved}


async def randomize(
    case_study_id: str,
    actor_id: Optional[str],
    *,
    treatment_fraction: float = 0.5,
    seed: Optional[int] = None,
    only_unassigned: bool = False,
    db: Optional[AsyncSession] = None,
) -> dict:
    """Randomly split active participants between control and treatment."""
    async with get_weblab_db(db) as db:
        participants = (
            await db.execute(
                select(Participant).where(
                    Participant.case_study_id == case_study_id, Participant.status == 'active'
                )
            )
        ).scalars().all()

        candidates = []
        for participant in participants:
            membership = await get_current_membership(case_study_id, participant.user_id, db=db)
            if only_unassigned and membership and membership.kind == 'treatment':
                continue
            candidates.append(participant)

        rng = random.Random(seed) if seed is not None else random.Random()
        ordered = list(candidates)
        rng.shuffle(ordered)
        cut = round(len(ordered) * treatment_fraction)
        treatment = [p.user_id for p in ordered[:cut]]
        control = [p.user_id for p in ordered[cut:]]

        await log_event(
            db,
            'membership.randomized',
            case_study_id=case_study_id,
            actor_id=actor_id,
            data={'treatment': len(treatment), 'control': len(control), 'seed': seed, 'fraction': treatment_fraction},
        )
        await db.commit()

    if treatment:
        await set_membership(case_study_id, treatment, 'treatment', actor_id, reason='randomized')
    if control:
        await set_membership(case_study_id, control, 'control', actor_id, reason='randomized')
    return {'treatment': len(treatment), 'control': len(control)}


async def end_participation(
    case_study_id: str, user_id: str, actor_id: Optional[str], db: Optional[AsyncSession] = None
) -> bool:
    async with get_weblab_db(db) as db:
        participant = (
            await db.execute(
                select(Participant).where(
                    Participant.case_study_id == case_study_id, Participant.user_id == user_id
                )
            )
        ).scalars().first()
        if not participant:
            return False
        stamp = now_ts()
        participant.status = 'ended'
        participant.left_at = stamp
        await db.execute(
            update(Membership)
            .where(Membership.participant_id == participant.id, Membership.effective_to.is_(None))
            .values(effective_to=stamp)
        )
        await log_event(
            db, 'participant.ended', case_study_id=case_study_id, user_id=user_id, actor_id=actor_id
        )
        await db.commit()
        return True


async def get_current_membership(
    case_study_id: str, user_id: str, db: Optional[AsyncSession] = None
) -> Optional[Membership]:
    async with get_weblab_db(db) as db:
        return (
            await db.execute(
                select(Membership)
                .where(
                    Membership.case_study_id == case_study_id,
                    Membership.user_id == user_id,
                    Membership.effective_to.is_(None),
                )
                .order_by(Membership.effective_from.desc())
            )
        ).scalars().first()


async def get_membership_history(
    case_study_id: str, user_id: str, db: Optional[AsyncSession] = None
) -> list[Membership]:
    async with get_weblab_db(db) as db:
        return list(
            (
                await db.execute(
                    select(Membership)
                    .where(Membership.case_study_id == case_study_id, Membership.user_id == user_id)
                    .order_by(Membership.effective_from.asc())
                )
            )
            .scalars()
            .all()
        )


async def list_participants(case_study_id: str, db: Optional[AsyncSession] = None) -> list[dict]:
    """Participants with their current arm and a count of arm changes."""
    async with get_weblab_db(db) as db:
        participants = (
            await db.execute(
                select(Participant)
                .where(Participant.case_study_id == case_study_id)
                .order_by(Participant.joined_at.asc())
            )
        ).scalars().all()

        rows = []
        for participant in participants:
            history = await get_membership_history(case_study_id, participant.user_id, db=db)
            current = next((m for m in history if m.effective_to is None), None)
            interventions = (
                await db.execute(
                    select(func.count()).select_from(Intervention).where(
                        Intervention.case_study_id == case_study_id, Intervention.user_id == participant.user_id
                    )
                )
            ).scalar() or 0
            accepted = (
                await db.execute(
                    select(func.count()).select_from(Intervention).where(
                        Intervention.case_study_id == case_study_id,
                        Intervention.user_id == participant.user_id,
                        Intervention.decision == 'accepted',
                    )
                )
            ).scalar() or 0
            tokens = (
                await db.execute(
                    select(func.coalesce(func.sum(UsageRecord.total_tokens), 0)).where(
                        UsageRecord.user_id == participant.user_id,
                        UsageRecord.created_at >= participant.joined_at,
                    )
                )
            ).scalar() or 0
            messages = (
                await db.execute(
                    select(func.count()).select_from(MessageRecord).where(
                        MessageRecord.user_id == participant.user_id,
                        MessageRecord.created_at >= participant.joined_at,
                    )
                )
            ).scalar() or 0
            rows.append(
                {
                    'id': participant.id,
                    'user_id': participant.user_id,
                    'user_name': participant.user_name,
                    'user_email': participant.user_email,
                    'status': participant.status,
                    'joined_at': participant.joined_at,
                    'left_at': participant.left_at,
                    'group_kind': current.kind if current else None,
                    'group_since': current.effective_from if current else None,
                    'membership_changes': max(len(history) - 1, 0),
                    'interventions_shown': interventions,
                    'interventions_accepted': accepted,
                    'total_tokens': int(tokens),
                    'total_messages': int(messages),
                }
            )
        return rows


####################
# Demand windows
####################


async def import_demand_windows(
    case_study_id: str,
    content: str,
    actor_id: Optional[str],
    *,
    filename: Optional[str] = None,
    timezone_name: Optional[str] = None,
    replace: bool = False,
    db: Optional[AsyncSession] = None,
) -> dict:
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            return {'error': 'Case study not found.'}

        tz_name = timezone_name or study.timezone or 'America/New_York'
        parsed = parse_demand_csv(content, tz_name)

        record = DemandWindowImport(
            id=new_id(),
            case_study_id=case_study_id,
            filename=filename,
            timezone=tz_name,
            row_count=len(parsed.windows),
            skipped_count=parsed.skipped,
            replaced=replace,
            raw_csv=content,
            warnings=parsed.warnings,
            imported_by=actor_id,
            imported_at=now_ts(),
        )
        db.add(record)
        # Flush so the windows below can reference this import row.
        await db.flush()

        if replace:
            # Deactivate rather than delete, so a past import stays auditable.
            await db.execute(
                update(DemandWindow)
                .where(DemandWindow.case_study_id == case_study_id, DemandWindow.active.is_(True))
                .values(active=False)
            )

        for window in parsed.windows:
            db.add(
                DemandWindow(
                    id=new_id(),
                    case_study_id=case_study_id,
                    import_id=record.id,
                    starts_at=window.starts_at,
                    ends_at=window.ends_at,
                    local_start=window.local_start,
                    local_end=window.local_end,
                    timezone=window.timezone,
                    label=window.label,
                    source='csv',
                    active=True,
                    created_by=actor_id,
                    created_at=now_ts(),
                )
            )

        await log_event(
            db,
            'demand_windows.imported',
            case_study_id=case_study_id,
            actor_id=actor_id,
            data={'filename': filename, 'imported': len(parsed.windows), 'skipped': parsed.skipped, 'replace': replace},
        )
        await db.commit()

        return {
            'import_id': record.id,
            'imported': len(parsed.windows),
            'skipped': parsed.skipped,
            'warnings': parsed.warnings,
            'timezone': tz_name,
        }


async def list_demand_windows(
    case_study_id: str, *, include_inactive: bool = False, db: Optional[AsyncSession] = None
) -> list[DemandWindow]:
    async with get_weblab_db(db) as db:
        query = select(DemandWindow).where(DemandWindow.case_study_id == case_study_id)
        if not include_inactive:
            query = query.where(DemandWindow.active.is_(True))
        return list((await db.execute(query.order_by(DemandWindow.starts_at.asc()))).scalars().all())


async def add_demand_window(
    case_study_id: str,
    starts_at: int,
    ends_at: int,
    label: Optional[str],
    actor_id: Optional[str],
    db: Optional[AsyncSession] = None,
) -> Optional[DemandWindow]:
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study or ends_at <= starts_at:
            return None
        zone = ZoneInfo(study.timezone or 'UTC')
        window = DemandWindow(
            id=new_id(),
            case_study_id=case_study_id,
            starts_at=starts_at,
            ends_at=ends_at,
            local_start=datetime.fromtimestamp(starts_at, zone).isoformat(),
            local_end=datetime.fromtimestamp(ends_at, zone).isoformat(),
            timezone=study.timezone,
            label=label,
            source='manual',
            active=True,
            created_by=actor_id,
            created_at=now_ts(),
        )
        db.add(window)
        await log_event(
            db, 'demand_window.added', case_study_id=case_study_id, actor_id=actor_id,
            data={'starts_at': starts_at, 'ends_at': ends_at, 'label': label},
        )
        await db.commit()
        return window


async def deactivate_demand_window(
    case_study_id: str, window_id: str, actor_id: Optional[str], db: Optional[AsyncSession] = None
) -> bool:
    async with get_weblab_db(db) as db:
        window = await db.get(DemandWindow, window_id)
        if not window or window.case_study_id != case_study_id:
            return False
        window.active = False
        await log_event(
            db, 'demand_window.removed', case_study_id=case_study_id, actor_id=actor_id, data={'window_id': window_id}
        )
        await db.commit()
        return True


async def find_active_window(
    case_study_id: str, at: Optional[int] = None, db: Optional[AsyncSession] = None
) -> Optional[DemandWindow]:
    """The demand window covering *at*, choosing the one that ends last."""
    at = at or now_ts()
    async with get_weblab_db(db) as db:
        return (
            await db.execute(
                select(DemandWindow)
                .where(
                    DemandWindow.case_study_id == case_study_id,
                    DemandWindow.active.is_(True),
                    DemandWindow.starts_at <= at,
                    DemandWindow.ends_at > at,
                )
                .order_by(DemandWindow.ends_at.desc())
            )
        ).scalars().first()


####################
# Usage mirroring
####################


def _extract_tokens(usage: Any) -> tuple[int, int, int]:
    """Pull (input, output, total) out of the many shapes providers return."""
    if isinstance(usage, str):
        try:
            usage = json.loads(usage)
        except (ValueError, TypeError):
            return 0, 0, 0
    if not isinstance(usage, dict):
        return 0, 0, 0

    def pick(*keys: str) -> int:
        for key in keys:
            value = usage.get(key)
            if isinstance(value, (int, float)):
                return int(value)
        return 0

    prompt_tokens = pick('input_tokens', 'prompt_tokens', 'promptTokens', 'prompt_eval_count')
    completion_tokens = pick('output_tokens', 'completion_tokens', 'completionTokens', 'eval_count')
    total = pick('total_tokens', 'totalTokens')
    if not total:
        total = prompt_tokens + completion_tokens
    return prompt_tokens, completion_tokens, total


async def record_usage(
    *,
    user_id: str,
    chat_id: Optional[str],
    message_id: Optional[str],
    model_id: Optional[str],
    usage: Any,
    created_at: Optional[int] = None,
    role: str = 'assistant',
) -> None:
    """Mirror one message into the study database.

    Called from the main app's message write path.  Never raises: a study
    bookkeeping problem must not break a user's chat.
    """
    try:
        record_id = f'{chat_id}-{message_id}' if chat_id and message_id else new_id()
        stamp = created_at or now_ts()
        input_tokens, output_tokens, total = _extract_tokens(usage)

        async with get_weblab_db() as db:
            # Only user prompts count towards message volume — recording the
            # assistant reply too would double every conversation turn.
            if role == 'user':
                existing_message = await db.get(MessageRecord, record_id)
                if existing_message is None:
                    db.add(
                        MessageRecord(
                            id=record_id,
                            user_id=user_id,
                            chat_id=chat_id,
                            message_id=message_id,
                            model_id=model_id,
                            role=role,
                            created_at=stamp,
                            recorded_at=now_ts(),
                        )
                    )
                elif model_id and not existing_message.model_id:
                    existing_message.model_id = model_id

            if total or input_tokens or output_tokens:
                existing = await db.get(UsageRecord, record_id)
                if existing is None:
                    db.add(
                        UsageRecord(
                            id=record_id,
                            user_id=user_id,
                            chat_id=chat_id,
                            message_id=message_id,
                            model_id=model_id,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens,
                            total_tokens=total,
                            created_at=stamp,
                            recorded_at=now_ts(),
                            raw_usage=usage if isinstance(usage, dict) else None,
                        )
                    )
                else:
                    # Streaming updates the same message repeatedly; keep the
                    # largest figures rather than double-counting.
                    existing.input_tokens = max(existing.input_tokens or 0, input_tokens)
                    existing.output_tokens = max(existing.output_tokens or 0, output_tokens)
                    existing.total_tokens = max(existing.total_tokens or 0, total)
                    existing.recorded_at = now_ts()
                    if isinstance(usage, dict):
                        existing.raw_usage = usage
            await db.commit()
    except Exception:
        log.exception('Web Lab: failed to mirror usage for user %s', user_id)


####################
# Intervention decision
####################


async def check_intervention(
    user_id: str, *, chat_id: Optional[str] = None, debug: bool = False, db: Optional[AsyncSession] = None
) -> InterventionCheckResponse:
    """Decide what the chat client should do before sending a message."""
    now = now_ts()
    trace: list[dict] = []

    async with get_weblab_db(db) as db:
        studies = (
            await db.execute(select(CaseStudy).where(CaseStudy.status == 'running'))
        ).scalars().all()

        if not studies:
            return InterventionCheckResponse(action='none', debug={'reason': 'no running case studies'} if debug else None)

        for study in studies:
            note: dict[str, Any] = {'case_study': study.name, 'id': study.id}

            participant = (
                await db.execute(
                    select(Participant).where(
                        Participant.case_study_id == study.id,
                        Participant.user_id == user_id,
                        Participant.status == 'active',
                    )
                )
            ).scalars().first()

            if not participant or participant.joined_at > now:
                note['skip'] = 'not an active participant'
                trace.append(note)
                continue

            # An active hold takes priority over everything else.
            postponement = (
                await db.execute(
                    select(Postponement)
                    .where(
                        Postponement.case_study_id == study.id,
                        Postponement.user_id == user_id,
                        Postponement.status == 'active',
                    )
                    .order_by(Postponement.ends_at.desc())
                )
            ).scalars().first()

            if postponement:
                if postponement.ends_at > now:
                    note['result'] = 'waiting'
                    trace.append(note)
                    return InterventionCheckResponse(
                        action='waiting',
                        case_study_id=study.id,
                        case_study_name=study.name,
                        intervention_id=postponement.intervention_id,
                        title=study.prompt_title or DEFAULT_PROMPT_TITLE,
                        body=study.waiting_body or DEFAULT_WAITING_BODY,
                        postpone_mode=postponement.mode,
                        ends_at=postponement.ends_at,
                        remaining_seconds=max(postponement.ends_at - now, 0),
                        allow_override=bool(study.allow_override),
                        debug={'trace': trace} if debug else None,
                    )
                postponement.status = 'completed'
                postponement.released_at = now
                postponement.release_reason = 'elapsed'
                postponement.honoured = True
                await log_event(
                    db, 'postponement.completed', case_study_id=study.id, user_id=user_id,
                    data={'postponement_id': postponement.id},
                )
                await db.commit()

            membership = (
                await db.execute(
                    select(Membership)
                    .where(
                        Membership.case_study_id == study.id,
                        Membership.user_id == user_id,
                        Membership.effective_to.is_(None),
                    )
                    .order_by(Membership.effective_from.desc())
                )
            ).scalars().first()

            note['arm'] = membership.kind if membership else None

            if not membership or membership.kind != 'treatment':
                note['skip'] = 'not in the treatment arm'
                trace.append(note)
                continue

            phase = current_phase(study, now)
            note['phase'] = phase
            if phase != 'treatment':
                note['skip'] = f'study is in the "{phase}" phase — no popups'
                trace.append(note)
                continue

            window = await find_active_window(study.id, now, db=db)
            note['demand_window'] = window.label if window else None
            if study.require_demand_window and window is None:
                note['skip'] = 'not inside a high-demand window'
                trace.append(note)
                continue

            last_shown = (
                await db.execute(
                    select(func.max(Intervention.shown_at)).where(
                        Intervention.case_study_id == study.id, Intervention.user_id == user_id
                    )
                )
            ).scalar()
            if last_shown:
                elapsed_minutes = (now - last_shown) / 60
                note['minutes_since_last_prompt'] = round(elapsed_minutes, 1)
                if elapsed_minutes < (study.reprompt_cooldown_minutes or 0):
                    note['skip'] = f'asked {round(elapsed_minutes, 1)}m ago, cooldown is {study.reprompt_cooldown_minutes}m'
                    trace.append(note)
                    continue

            probability = study.trigger_probability if study.trigger_probability is not None else 1.0
            if probability < 1.0:
                roll = random.random()
                note['probability'] = probability
                note['roll'] = round(roll, 3)
                if roll >= probability:
                    note['skip'] = 'lost the probability roll'
                    trace.append(note)
                    continue

            postpone_seconds, mode = _compute_postpone_seconds(study, window, now)
            note['result'] = 'prompt'
            note['postpone_seconds'] = postpone_seconds
            trace.append(note)

            intervention = Intervention(
                id=new_id(),
                case_study_id=study.id,
                participant_id=participant.id,
                user_id=user_id,
                group_id=membership.group_id,
                group_kind=membership.kind,
                membership_id=membership.id,
                demand_window_id=window.id if window else None,
                demand_window_label=window.label if window else None,
                demand_window_ends_at=window.ends_at if window else None,
                chat_id=chat_id,
                shown_at=now,
                decision='pending',
                offered_mode=mode,
                offered_seconds=postpone_seconds,
                prompt_text=study.prompt_body or DEFAULT_PROMPT_BODY,
            )
            db.add(intervention)
            await log_event(
                db,
                'intervention.shown',
                case_study_id=study.id,
                user_id=user_id,
                data={'intervention_id': intervention.id, 'window': window.label if window else None},
            )
            await db.commit()

            return InterventionCheckResponse(
                action='prompt',
                case_study_id=study.id,
                case_study_name=study.name,
                intervention_id=intervention.id,
                title=study.prompt_title or DEFAULT_PROMPT_TITLE,
                body=study.prompt_body or DEFAULT_PROMPT_BODY,
                accept_label=study.accept_label or DEFAULT_ACCEPT_LABEL,
                decline_label=study.decline_label or DEFAULT_DECLINE_LABEL,
                postpone_seconds=postpone_seconds,
                postpone_mode=mode,
                ends_at=now + postpone_seconds,
                allow_override=bool(study.allow_override),
                demand_window_label=window.label if window else None,
                debug={'trace': trace} if debug else None,
            )

    return InterventionCheckResponse(action='none', debug={'trace': trace} if debug else None)


def _compute_postpone_seconds(
    study: CaseStudy, window: Optional[DemandWindow], now: int
) -> tuple[int, str]:
    """How long the hold should run, per the study's postponement mode.

    ``fixed`` uses the configured number of minutes.  ``window_end`` runs until
    the current high-demand window closes, clamped by the study's floor and
    ceiling — and falls back to fixed if no window is in force.
    """
    if study.postpone_mode == 'window_end' and window is not None:
        seconds = max(window.ends_at - now, 0)
        floor = int((study.postpone_min_minutes or 0) * 60)
        seconds = max(seconds, floor)
        if study.postpone_max_minutes:
            seconds = min(seconds, int(study.postpone_max_minutes * 60))
        return int(seconds), 'window_end'
    return int((study.postpone_minutes or 5.0) * 60), 'fixed'


async def record_decision(
    intervention_id: str,
    decision: str,
    user_id: str,
    *,
    client_meta: Optional[dict] = None,
    db: Optional[AsyncSession] = None,
) -> dict:
    """Record what the user clicked, and start a hold if they accepted."""
    now = now_ts()
    async with get_weblab_db(db) as db:
        intervention = await db.get(Intervention, intervention_id)
        if not intervention or intervention.user_id != user_id:
            return {'ok': False, 'error': 'Unknown intervention.'}

        if intervention.decision != 'pending':
            return {
                'ok': True,
                'decision': intervention.decision,
                'already_recorded': True,
            }

        intervention.decision = decision
        intervention.decided_at = now
        intervention.response_seconds = max(now - intervention.shown_at, 0)
        if client_meta:
            intervention.client_meta = client_meta

        result: dict[str, Any] = {'ok': True, 'decision': decision}

        if decision == 'accepted':
            study = await db.get(CaseStudy, intervention.case_study_id)
            seconds = intervention.offered_seconds or int((study.postpone_minutes if study else 5.0) * 60)
            postponement = Postponement(
                id=new_id(),
                intervention_id=intervention.id,
                case_study_id=intervention.case_study_id,
                user_id=user_id,
                started_at=now,
                ends_at=now + seconds,
                mode=intervention.offered_mode or 'fixed',
                status='active',
            )
            db.add(postponement)
            result['postponement_id'] = postponement.id
            result['ends_at'] = postponement.ends_at
            result['remaining_seconds'] = seconds

        await log_event(
            db,
            f'intervention.{decision}',
            case_study_id=intervention.case_study_id,
            user_id=user_id,
            data={
                'intervention_id': intervention.id,
                'response_seconds': intervention.response_seconds,
                'window': intervention.demand_window_label,
            },
        )
        await db.commit()
        return result


async def release_postponement(
    user_id: str, reason: str = 'elapsed', *, case_study_id: Optional[str] = None, db: Optional[AsyncSession] = None
) -> dict:
    """Close out an active hold — either it ran its course or the user overrode it."""
    now = now_ts()
    async with get_weblab_db(db) as db:
        query = select(Postponement).where(
            Postponement.user_id == user_id, Postponement.status == 'active'
        )
        if case_study_id:
            query = query.where(Postponement.case_study_id == case_study_id)
        rows = (await db.execute(query)).scalars().all()

        released = 0
        for postponement in rows:
            elapsed = postponement.ends_at <= now
            postponement.status = 'completed' if (reason == 'elapsed' or elapsed) else 'overridden'
            postponement.released_at = now
            postponement.release_reason = reason
            postponement.honoured = elapsed
            released += 1
            await log_event(
                db,
                'postponement.overridden' if postponement.status == 'overridden' else 'postponement.completed',
                case_study_id=postponement.case_study_id,
                user_id=user_id,
                data={
                    'postponement_id': postponement.id,
                    'reason': reason,
                    'seconds_waited': max(now - postponement.started_at, 0),
                    'seconds_remaining': max(postponement.ends_at - now, 0),
                },
            )
        await db.commit()
        return {'released': released}
