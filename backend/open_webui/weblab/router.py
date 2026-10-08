"""HTTP surface for the Web Lab study.

Admin routes drive the dashboard; the three user-facing routes at the bottom
are what the chat client calls before and after sending a message.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.weblab import analytics, backup, service
from open_webui.weblab.db import WEBLAB_DB_PATH, get_weblab_db
from open_webui.weblab.demand_csv import parse_demand_csv
from open_webui.weblab.models import (
    CaseStudy,
    DemandWindow,
    Intervention,
    InterventionCheckResponse,
    Membership,
    Participant,
    Postponement,
    StudyEvent,
    StudyGroup,
    new_id,
    now_ts,
)
from pydantic import BaseModel
from sqlalchemy import desc, select

log = logging.getLogger(__name__)

router = APIRouter()


####################
# Request bodies
####################


class CaseStudyForm(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    timezone: Optional[str] = None
    starts_at: Optional[int] = None
    ends_at: Optional[int] = None
    intervention_starts_at: Optional[int] = None
    intervention_ends_at: Optional[int] = None
    postpone_mode: Optional[str] = None
    postpone_minutes: Optional[float] = None
    postpone_min_minutes: Optional[float] = None
    postpone_max_minutes: Optional[float] = None
    reprompt_cooldown_minutes: Optional[float] = None
    require_demand_window: Optional[bool] = None
    trigger_probability: Optional[float] = None
    allow_override: Optional[bool] = None
    prompt_title: Optional[str] = None
    prompt_body: Optional[str] = None
    accept_label: Optional[str] = None
    decline_label: Optional[str] = None
    waiting_body: Optional[str] = None


class EnrollForm(BaseModel):
    user_ids: list[str] = []
    all_users: bool = False
    group_kind: str = 'control'
    joined_at: Optional[int] = None


class MembershipForm(BaseModel):
    user_ids: list[str]
    group_kind: str
    reason: Optional[str] = None
    effective_at: Optional[int] = None


class RandomizeForm(BaseModel):
    treatment_fraction: float = 0.5
    seed: Optional[int] = None
    only_unassigned: bool = False


class DemandWindowForm(BaseModel):
    starts_at: int
    ends_at: int
    label: Optional[str] = None


class DecisionForm(BaseModel):
    intervention_id: str
    decision: str  # accepted | declined | dismissed
    client_meta: Optional[dict] = None


class ReleaseForm(BaseModel):
    case_study_id: Optional[str] = None
    reason: str = 'elapsed'


####################
# Case studies
####################


@router.get('/case-studies')
async def list_case_studies(user=Depends(get_admin_user)):
    return await service.list_case_studies()


@router.post('/case-studies')
async def create_case_study(form: CaseStudyForm, user=Depends(get_admin_user)):
    return await service.create_case_study(form.model_dump(exclude_none=True), user.id)


@router.get('/case-studies/{case_study_id}')
async def get_case_study(case_study_id: str, user=Depends(get_admin_user)):
    async with get_weblab_db() as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            raise HTTPException(status_code=404, detail='Case study not found')
        groups = await service.get_groups(case_study_id, db)
        return {
            **service._study_dict(study),
            'phase': service.current_phase(study),
            'groups': [
                {'id': g.id, 'name': g.name, 'kind': g.kind, 'description': g.description} for g in groups
            ],
        }


@router.put('/case-studies/{case_study_id}')
async def update_case_study(case_study_id: str, form: CaseStudyForm, user=Depends(get_admin_user)):
    updated = await service.update_case_study(case_study_id, form.model_dump(exclude_unset=True), user.id)
    if updated is None:
        raise HTTPException(status_code=404, detail='Case study not found')
    return updated


@router.delete('/case-studies/{case_study_id}')
async def archive_case_study(case_study_id: str, user=Depends(get_admin_user)):
    if not await service.delete_case_study(case_study_id, user.id):
        raise HTTPException(status_code=404, detail='Case study not found')
    return {'ok': True}


####################
# Participants & arms
####################


@router.get('/case-studies/{case_study_id}/participants')
async def list_participants(case_study_id: str, user=Depends(get_admin_user)):
    return await service.list_participants(case_study_id)


@router.post('/case-studies/{case_study_id}/participants')
async def enroll(case_study_id: str, form: EnrollForm, user=Depends(get_admin_user)):
    if form.all_users:
        result = await Users.get_users()
        candidates = [
            {'id': u.id, 'email': u.email, 'name': u.name}
            for u in result.get('users', [])
            if u.role != 'pending'
        ]
    else:
        candidates = []
        for user_id in form.user_ids:
            record = await Users.get_user_by_id(user_id)
            candidates.append(
                {'id': user_id, 'email': record.email if record else None, 'name': record.name if record else None}
            )

    return await service.enroll_participants(
        case_study_id, candidates, user.id, group_kind=form.group_kind, joined_at=form.joined_at
    )


@router.delete('/case-studies/{case_study_id}/participants/{user_id}')
async def end_participation(case_study_id: str, user_id: str, user=Depends(get_admin_user)):
    if not await service.end_participation(case_study_id, user_id, user.id):
        raise HTTPException(status_code=404, detail='Participant not found')
    return {'ok': True}


@router.post('/case-studies/{case_study_id}/membership')
async def set_membership(case_study_id: str, form: MembershipForm, user=Depends(get_admin_user)):
    return await service.set_membership(
        case_study_id,
        form.user_ids,
        form.group_kind,
        user.id,
        reason=form.reason,
        effective_at=form.effective_at,
    )


@router.post('/case-studies/{case_study_id}/randomize')
async def randomize(case_study_id: str, form: RandomizeForm, user=Depends(get_admin_user)):
    return await service.randomize(
        case_study_id,
        user.id,
        treatment_fraction=form.treatment_fraction,
        seed=form.seed,
        only_unassigned=form.only_unassigned,
    )


@router.get('/case-studies/{case_study_id}/participants/{user_id}/history')
async def membership_history(case_study_id: str, user_id: str, user=Depends(get_admin_user)):
    history = await service.get_membership_history(case_study_id, user_id)
    async with get_weblab_db() as db:
        interventions = (
            await db.execute(
                select(Intervention)
                .where(Intervention.case_study_id == case_study_id, Intervention.user_id == user_id)
                .order_by(desc(Intervention.shown_at))
                .limit(200)
            )
        ).scalars().all()
        postponements = (
            await db.execute(
                select(Postponement)
                .where(Postponement.case_study_id == case_study_id, Postponement.user_id == user_id)
                .order_by(desc(Postponement.started_at))
                .limit(200)
            )
        ).scalars().all()
    return {
        'memberships': [
            {
                'id': m.id, 'kind': m.kind, 'group_id': m.group_id,
                'effective_from': m.effective_from, 'effective_to': m.effective_to,
                'reason': m.reason, 'changed_by': m.changed_by,
            }
            for m in history
        ],
        'interventions': [
            {
                'id': i.id, 'shown_at': i.shown_at, 'decision': i.decision, 'decided_at': i.decided_at,
                'response_seconds': i.response_seconds, 'offered_seconds': i.offered_seconds,
                'offered_mode': i.offered_mode, 'demand_window_label': i.demand_window_label,
                'group_kind': i.group_kind, 'chat_id': i.chat_id,
            }
            for i in interventions
        ],
        'postponements': [
            {
                'id': p.id, 'started_at': p.started_at, 'ends_at': p.ends_at, 'mode': p.mode,
                'status': p.status, 'released_at': p.released_at, 'honoured': p.honoured,
                'release_reason': p.release_reason,
            }
            for p in postponements
        ],
    }


@router.get('/candidates')
async def list_candidate_users(
    case_study_id: Optional[str] = None, query: Optional[str] = None, user=Depends(get_admin_user)
):
    """Users who can be enrolled, flagged with whether they already are."""
    result = await Users.get_users(filter={'query': query} if query else None)
    users = result.get('users', [])

    enrolled: dict[str, str] = {}
    if case_study_id:
        async with get_weblab_db() as db:
            rows = (
                await db.execute(
                    select(Participant.user_id, Participant.status).where(
                        Participant.case_study_id == case_study_id
                    )
                )
            ).all()
            enrolled = {row[0]: row[1] for row in rows}

    return [
        {
            'id': u.id,
            'name': u.name,
            'email': u.email,
            'role': u.role,
            'last_active_at': u.last_active_at,
            'enrolled': enrolled.get(u.id),
        }
        for u in users
    ]


####################
# Demand windows
####################


@router.get('/case-studies/{case_study_id}/demand-windows')
async def list_demand_windows(
    case_study_id: str, include_inactive: bool = False, user=Depends(get_admin_user)
):
    windows = await service.list_demand_windows(case_study_id, include_inactive=include_inactive)
    now = now_ts()
    return [
        {
            'id': w.id, 'starts_at': w.starts_at, 'ends_at': w.ends_at,
            'local_start': w.local_start, 'local_end': w.local_end, 'timezone': w.timezone,
            'label': w.label, 'source': w.source, 'active': w.active,
            'state': 'live' if w.starts_at <= now < w.ends_at else ('past' if w.ends_at <= now else 'upcoming'),
            'duration_minutes': round((w.ends_at - w.starts_at) / 60, 1),
        }
        for w in windows
    ]


@router.post('/case-studies/{case_study_id}/demand-windows/preview')
async def preview_demand_csv(
    case_study_id: str,
    file: UploadFile = File(...),
    timezone: Optional[str] = Query(None),
    user=Depends(get_admin_user),
):
    """Parse a CSV and show what would be imported, without writing anything."""
    content = (await file.read()).decode('utf-8-sig', errors='replace')
    async with get_weblab_db() as db:
        study = await db.get(CaseStudy, case_study_id)
    tz_name = timezone or (study.timezone if study else 'America/New_York')
    parsed = parse_demand_csv(content, tz_name)
    return {
        'timezone': tz_name,
        'skipped': parsed.skipped,
        'warnings': parsed.warnings,
        'windows': [
            {
                'row': w.row_number, 'starts_at': w.starts_at, 'ends_at': w.ends_at,
                'local_start': w.local_start, 'local_end': w.local_end,
                'label': w.label, 'duration_minutes': round((w.ends_at - w.starts_at) / 60, 1),
            }
            for w in parsed.windows
        ],
    }


@router.post('/case-studies/{case_study_id}/demand-windows/import')
async def import_demand_csv(
    case_study_id: str,
    file: UploadFile = File(...),
    timezone: Optional[str] = Query(None),
    replace: bool = Query(False),
    user=Depends(get_admin_user),
):
    content = (await file.read()).decode('utf-8-sig', errors='replace')
    result = await service.import_demand_windows(
        case_study_id, content, user.id, filename=file.filename, timezone_name=timezone, replace=replace
    )
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.post('/case-studies/{case_study_id}/demand-windows')
async def add_demand_window(case_study_id: str, form: DemandWindowForm, user=Depends(get_admin_user)):
    window = await service.add_demand_window(
        case_study_id, form.starts_at, form.ends_at, form.label, user.id
    )
    if window is None:
        raise HTTPException(status_code=400, detail='Could not add that window — check the case study and that end is after start.')
    return {'id': window.id, 'starts_at': window.starts_at, 'ends_at': window.ends_at, 'label': window.label}


@router.delete('/case-studies/{case_study_id}/demand-windows/{window_id}')
async def remove_demand_window(case_study_id: str, window_id: str, user=Depends(get_admin_user)):
    if not await service.deactivate_demand_window(case_study_id, window_id, user.id):
        raise HTTPException(status_code=404, detail='Window not found')
    return {'ok': True}


@router.get('/case-studies/{case_study_id}/demand-windows/imports')
async def list_demand_imports(case_study_id: str, user=Depends(get_admin_user)):
    from open_webui.weblab.models import DemandWindowImport

    async with get_weblab_db() as db:
        rows = (
            await db.execute(
                select(DemandWindowImport)
                .where(DemandWindowImport.case_study_id == case_study_id)
                .order_by(desc(DemandWindowImport.imported_at))
            )
        ).scalars().all()
    return [
        {
            'id': r.id, 'filename': r.filename, 'timezone': r.timezone, 'row_count': r.row_count,
            'skipped_count': r.skipped_count, 'replaced': r.replaced, 'warnings': r.warnings,
            'imported_at': r.imported_at,
        }
        for r in rows
    ]


####################
# Analytics
####################


@router.get('/usage/overview')
async def usage_overview(
    start: Optional[int] = None,
    end: Optional[int] = None,
    case_study_id: Optional[str] = None,
    group_kind: Optional[str] = None,
    timezone: str = 'America/New_York',
    user=Depends(get_admin_user),
):
    return await analytics.usage_overview(
        start=start, end=end, case_study_id=case_study_id, group_kind=group_kind, timezone_name=timezone
    )


@router.get('/case-studies/{case_study_id}/report')
async def case_study_report(case_study_id: str, user=Depends(get_admin_user)):
    report = await analytics.case_study_report(case_study_id)
    if not report:
        raise HTTPException(status_code=404, detail='Case study not found')
    return report


@router.get('/case-studies/{case_study_id}/interventions')
async def list_interventions(
    case_study_id: str, limit: int = 200, skip: int = 0, user=Depends(get_admin_user)
):
    async with get_weblab_db() as db:
        rows = (
            await db.execute(
                select(Intervention)
                .where(Intervention.case_study_id == case_study_id)
                .order_by(desc(Intervention.shown_at))
                .offset(skip)
                .limit(min(limit, 1000))
            )
        ).scalars().all()
        names = {
            row[0]: row[1]
            for row in (
                await db.execute(
                    select(Participant.user_id, Participant.user_name).where(
                        Participant.case_study_id == case_study_id
                    )
                )
            ).all()
        }
    return [
        {
            'id': i.id, 'user_id': i.user_id, 'user_name': names.get(i.user_id),
            'group_kind': i.group_kind, 'shown_at': i.shown_at, 'decision': i.decision,
            'decided_at': i.decided_at, 'response_seconds': i.response_seconds,
            'offered_mode': i.offered_mode, 'offered_seconds': i.offered_seconds,
            'demand_window_label': i.demand_window_label, 'chat_id': i.chat_id,
        }
        for i in rows
    ]


@router.get('/case-studies/{case_study_id}/events')
async def list_events(case_study_id: str, limit: int = 300, skip: int = 0, user=Depends(get_admin_user)):
    async with get_weblab_db() as db:
        rows = (
            await db.execute(
                select(StudyEvent)
                .where(StudyEvent.case_study_id == case_study_id)
                .order_by(desc(StudyEvent.created_at))
                .offset(skip)
                .limit(min(limit, 2000))
            )
        ).scalars().all()
    return [
        {
            'id': e.id, 'type': e.type, 'user_id': e.user_id, 'actor_id': e.actor_id,
            'data': e.data, 'created_at': e.created_at,
        }
        for e in rows
    ]


####################
# Export & database
####################


@router.get('/case-studies/{case_study_id}/export')
async def export_case_study(case_study_id: str, format: str = 'json', user=Depends(get_admin_user)):
    """Everything about one case study, for offline analysis."""
    from open_webui.weblab.models import DemandWindowImport, MessageRecord, UsageRecord

    async with get_weblab_db() as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            raise HTTPException(status_code=404, detail='Case study not found')

        async def rows_of(model, *filters):
            result = await db.execute(select(model).where(*filters))
            return [
                {c.name: getattr(row, c.name) for c in model.__table__.columns}
                for row in result.scalars().all()
            ]

        participants = await rows_of(Participant, Participant.case_study_id == case_study_id)
        user_ids = [p['user_id'] for p in participants]

        payload = {
            'case_study': service._study_dict(study),
            'groups': await rows_of(StudyGroup, StudyGroup.case_study_id == case_study_id),
            'participants': participants,
            'memberships': await rows_of(Membership, Membership.case_study_id == case_study_id),
            'demand_windows': await rows_of(DemandWindow, DemandWindow.case_study_id == case_study_id),
            'demand_imports': [
                {k: v for k, v in row.items() if k != 'raw_csv'}
                for row in await rows_of(DemandWindowImport, DemandWindowImport.case_study_id == case_study_id)
            ],
            'interventions': await rows_of(Intervention, Intervention.case_study_id == case_study_id),
            'postponements': await rows_of(Postponement, Postponement.case_study_id == case_study_id),
            'events': await rows_of(StudyEvent, StudyEvent.case_study_id == case_study_id),
            'usage_records': await rows_of(UsageRecord, UsageRecord.user_id.in_(user_ids)) if user_ids else [],
            'message_records': await rows_of(MessageRecord, MessageRecord.user_id.in_(user_ids)) if user_ids else [],
            'exported_at': now_ts(),
        }

    if format == 'csv':
        # One flat participant-level file, which is what most analyses start from.
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                'user_id', 'user_name', 'user_email', 'joined_at', 'left_at', 'status',
                'current_arm', 'arm_changes', 'interventions_shown', 'accepted', 'declined',
                'postponements', 'total_tokens', 'total_messages',
            ]
        )
        summary = await service.list_participants(case_study_id)
        by_user_interventions: dict[str, dict] = {}
        for row in payload['interventions']:
            entry = by_user_interventions.setdefault(row['user_id'], {'declined': 0})
            if row['decision'] == 'declined':
                entry['declined'] += 1
        postponement_counts: dict[str, int] = {}
        for row in payload['postponements']:
            postponement_counts[row['user_id']] = postponement_counts.get(row['user_id'], 0) + 1

        for row in summary:
            writer.writerow(
                [
                    row['user_id'], row['user_name'], row['user_email'], row['joined_at'], row['left_at'],
                    row['status'], row['group_kind'], row['membership_changes'], row['interventions_shown'],
                    row['interventions_accepted'],
                    by_user_interventions.get(row['user_id'], {}).get('declined', 0),
                    postponement_counts.get(row['user_id'], 0),
                    row['total_tokens'], row['total_messages'],
                ]
            )
        buffer.seek(0)
        return StreamingResponse(
            iter([buffer.getvalue()]),
            media_type='text/csv',
            headers={'Content-Disposition': f'attachment; filename="weblab-{case_study_id}.csv"'},
        )

    return payload


@router.get('/db/info')
async def db_info(user=Depends(get_admin_user)):
    from open_webui.weblab.db import SCHEMA_VERSION

    info = backup.database_info()
    async with get_weblab_db() as db:
        counts = {}
        from open_webui.weblab.models import MessageRecord, UsageRecord
        from sqlalchemy import func as sql_func

        for label, model in (
            ('case_studies', CaseStudy), ('participants', Participant), ('memberships', Membership),
            ('demand_windows', DemandWindow), ('interventions', Intervention),
            ('postponements', Postponement), ('usage_records', UsageRecord),
            ('message_records', MessageRecord), ('events', StudyEvent),
        ):
            counts[label] = (await db.execute(select(sql_func.count()).select_from(model))).scalar() or 0
    return {**info, 'schema_version': SCHEMA_VERSION, 'row_counts': counts}


@router.get('/db/backups')
async def list_backups(user=Depends(get_admin_user)):
    return backup.list_backups()


@router.post('/db/backups')
async def create_backup(user=Depends(get_admin_user)):
    import asyncio

    result = await asyncio.to_thread(backup.create_backup)
    if not result.get('ok'):
        raise HTTPException(status_code=500, detail=result.get('error', 'Snapshot failed'))
    return result


@router.get('/db/backups/{filename}/verify')
async def verify_backup(filename: str, user=Depends(get_admin_user)):
    import asyncio

    return await asyncio.to_thread(backup.verify_backup, filename)


@router.post('/db/backups/{filename}/restore')
async def restore_backup(filename: str, user=Depends(get_admin_user)):
    import asyncio

    result = await asyncio.to_thread(backup.restore_backup, filename)
    if not result.get('ok'):
        raise HTTPException(status_code=400, detail=result.get('error', 'Restore failed'))
    return result


@router.get('/db/download')
async def download_database(user=Depends(get_admin_user)):
    """Download a consistent snapshot of the whole study database."""
    import asyncio

    snapshot = await asyncio.to_thread(backup.create_backup, 'download')
    if not snapshot.get('ok'):
        raise HTTPException(status_code=500, detail=snapshot.get('error', 'Snapshot failed'))
    return FileResponse(
        snapshot['path'], media_type='application/x-sqlite3', filename=snapshot['filename']
    )


####################
# User-facing
####################


@router.get('/check', response_model=InterventionCheckResponse)
async def check(chat_id: Optional[str] = None, debug: bool = False, user=Depends(get_verified_user)):
    """Called by the chat client before a message is sent."""
    return await service.check_intervention(user.id, chat_id=chat_id, debug=debug)


@router.post('/decision')
async def decision(form: DecisionForm, user=Depends(get_verified_user)):
    if form.decision not in ('accepted', 'declined', 'dismissed'):
        raise HTTPException(status_code=400, detail='Unknown decision')
    result = await service.record_decision(
        form.intervention_id, form.decision, user.id, client_meta=form.client_meta
    )
    if not result.get('ok'):
        raise HTTPException(status_code=404, detail=result.get('error', 'Unknown intervention'))
    return result


@router.post('/release')
async def release(form: ReleaseForm, user=Depends(get_verified_user)):
    """Close an active hold: the timer finished, or the user chose to send anyway."""
    return await service.release_postponement(user.id, form.reason, case_study_id=form.case_study_id)


@router.get('/debug')
async def debug_check(user=Depends(get_admin_user)):
    """Why the current admin would or would not see a popup right now."""
    return await service.check_intervention(user.id, debug=True)
