"""Read-side of the study database: usage monitoring and A/B comparison.

Everything here reads only the study's own tables, so the dashboard keeps
working — and keeps telling the truth about the study period — even if the
main Open WebUI database is later reset or upgraded.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from open_webui.weblab.db import get_weblab_db
from open_webui.weblab.models import (
    CaseStudy,
    DemandWindow,
    Intervention,
    Membership,
    MessageRecord,
    Participant,
    Postponement,
    UsageRecord,
)
from sqlalchemy import Float, and_, case, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = fraction * (len(sorted_values) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(sorted_values[int(position)])
    return float(sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low))


def _summarize(values: list[float]) -> dict:
    """Distribution summary used for both per-user and per-message token spreads."""
    if not values:
        return {
            'count': 0, 'sum': 0, 'mean': 0, 'min': 0, 'max': 0,
            'p25': 0, 'median': 0, 'p75': 0, 'p90': 0, 'p95': 0, 'stddev': 0,
        }
    ordered = sorted(values)
    total = float(sum(ordered))
    mean = total / len(ordered)
    variance = sum((v - mean) ** 2 for v in ordered) / len(ordered)
    return {
        'count': len(ordered),
        'sum': round(total, 2),
        'mean': round(mean, 2),
        'min': round(ordered[0], 2),
        'max': round(ordered[-1], 2),
        'p25': round(_percentile(ordered, 0.25), 2),
        'median': round(_percentile(ordered, 0.5), 2),
        'p75': round(_percentile(ordered, 0.75), 2),
        'p90': round(_percentile(ordered, 0.90), 2),
        'p95': round(_percentile(ordered, 0.95), 2),
        'stddev': round(math.sqrt(variance), 2),
    }


def _histogram(values: list[float], bucket_count: int = 12) -> list[dict]:
    """Equal-width buckets over the observed range, ready to plot as bars."""
    if not values:
        return []
    low, high = min(values), max(values)
    if high <= low:
        return [{'start': low, 'end': high, 'count': len(values), 'label': f'{int(low):,}'}]

    # A round-ish bucket width reads better on an axis than an arbitrary one.
    raw_width = (high - low) / bucket_count
    magnitude = 10 ** math.floor(math.log10(raw_width)) if raw_width > 0 else 1
    for step in (1, 2, 2.5, 5, 10):
        width = magnitude * step
        if width >= raw_width:
            break
    start = math.floor(low / width) * width
    buckets: list[dict] = []
    edge = start
    while edge <= high:
        buckets.append({'start': edge, 'end': edge + width, 'count': 0})
        edge += width

    for value in values:
        index = min(int((value - start) / width), len(buckets) - 1)
        buckets[max(index, 0)]['count'] += 1

    for bucket in buckets:
        bucket['label'] = f'{int(bucket["start"]):,}–{int(bucket["end"]):,}'
    return buckets


async def _scope_user_ids(
    db: AsyncSession, case_study_id: Optional[str], group_kind: Optional[str], at: Optional[int]
) -> Optional[list[str]]:
    """User ids in scope: everyone (None), a study's participants, or one arm.

    When *group_kind* is given, arm membership is evaluated as of *at* using
    the membership history — so a report about week 1 reflects who was in the
    treatment arm during week 1, not who is in it today.
    """
    if not case_study_id:
        return None

    if not group_kind:
        rows = (
            await db.execute(select(Participant.user_id).where(Participant.case_study_id == case_study_id))
        ).scalars().all()
        return list(rows)

    query = select(Membership.user_id).where(
        Membership.case_study_id == case_study_id, Membership.kind == group_kind
    )
    if at is not None:
        query = query.where(
            Membership.effective_from <= at,
            or_(Membership.effective_to.is_(None), Membership.effective_to > at),
        )
    else:
        query = query.where(Membership.effective_to.is_(None))
    return list((await db.execute(query)).scalars().unique().all())


async def usage_overview(
    *,
    start: Optional[int] = None,
    end: Optional[int] = None,
    case_study_id: Optional[str] = None,
    group_kind: Optional[str] = None,
    timezone_name: str = 'America/New_York',
    db: Optional[AsyncSession] = None,
) -> dict:
    """Headline usage figures plus the distributions the dashboard plots."""
    zone = ZoneInfo(timezone_name)

    async with get_weblab_db(db) as db:
        if case_study_id and (start is None or end is None):
            study = await db.get(CaseStudy, case_study_id)
            if study:
                start = start if start is not None else study.starts_at
                end = end if end is not None else study.ends_at
                timezone_name = study.timezone or timezone_name
                zone = ZoneInfo(timezone_name)

        user_ids = await _scope_user_ids(db, case_study_id, group_kind, end or start)
        if user_ids is not None and not user_ids:
            return _empty_overview(timezone_name, start, end)

        def bounded(query, column):
            if start is not None:
                query = query.where(column >= start)
            if end is not None:
                query = query.where(column <= end)
            if user_ids is not None:
                query = query.where(UsageRecord.user_id.in_(user_ids) if column is UsageRecord.created_at else MessageRecord.user_id.in_(user_ids))
            return query

        # ── Per-user totals ──────────────────────────────────────────────
        usage_rows = (
            await db.execute(
                bounded(
                    select(
                        UsageRecord.user_id,
                        func.sum(UsageRecord.total_tokens),
                        func.sum(UsageRecord.input_tokens),
                        func.sum(UsageRecord.output_tokens),
                        func.count(),
                    ).group_by(UsageRecord.user_id),
                    UsageRecord.created_at,
                )
            )
        ).all()

        message_rows = (
            await db.execute(
                bounded(
                    select(MessageRecord.user_id, func.count()).group_by(MessageRecord.user_id),
                    MessageRecord.created_at,
                )
            )
        ).all()
        messages_by_user = {row[0]: int(row[1]) for row in message_rows}

        per_user = []
        for user_id, total, input_tokens, output_tokens, count in usage_rows:
            per_user.append(
                {
                    'user_id': user_id,
                    'total_tokens': int(total or 0),
                    'input_tokens': int(input_tokens or 0),
                    'output_tokens': int(output_tokens or 0),
                    'messages_with_usage': int(count or 0),
                    'messages': messages_by_user.get(user_id, int(count or 0)),
                }
            )
        # Users who chatted but whose provider reported no token usage.
        for user_id, count in messages_by_user.items():
            if not any(entry['user_id'] == user_id for entry in per_user):
                per_user.append(
                    {
                        'user_id': user_id, 'total_tokens': 0, 'input_tokens': 0,
                        'output_tokens': 0, 'messages_with_usage': 0, 'messages': count,
                    }
                )

        # Attach names from the study's own participant records.
        if per_user:
            identities = (
                await db.execute(
                    select(Participant.user_id, Participant.user_name, Participant.user_email).where(
                        Participant.user_id.in_([e['user_id'] for e in per_user])
                    )
                )
            ).all()
            lookup = {row[0]: {'name': row[1], 'email': row[2]} for row in identities}
            for entry in per_user:
                identity = lookup.get(entry['user_id'], {})
                entry['user_name'] = identity.get('name')
                entry['user_email'] = identity.get('email')

        per_user.sort(key=lambda e: e['total_tokens'], reverse=True)

        # ── Distributions ────────────────────────────────────────────────
        user_token_values = [float(e['total_tokens']) for e in per_user]
        message_token_rows = (
            await db.execute(
                bounded(select(UsageRecord.total_tokens), UsageRecord.created_at)
            )
        ).scalars().all()
        message_token_values = [float(v or 0) for v in message_token_rows]

        # ── Time series ──────────────────────────────────────────────────
        daily: dict[str, dict] = {}
        hourly = [{'hour': h, 'messages': 0, 'tokens': 0} for h in range(24)]

        usage_points = (
            await db.execute(
                bounded(select(UsageRecord.created_at, UsageRecord.total_tokens), UsageRecord.created_at)
            )
        ).all()
        message_points = (
            await db.execute(
                bounded(select(MessageRecord.created_at), MessageRecord.created_at)
            )
        ).scalars().all()

        for stamp, tokens in usage_points:
            local = datetime.fromtimestamp(stamp, zone)
            key = local.strftime('%Y-%m-%d')
            entry = daily.setdefault(key, {'date': key, 'messages': 0, 'tokens': 0, 'users': set()})
            entry['tokens'] += int(tokens or 0)
            hourly[local.hour]['tokens'] += int(tokens or 0)

        for stamp in message_points:
            local = datetime.fromtimestamp(stamp, zone)
            key = local.strftime('%Y-%m-%d')
            entry = daily.setdefault(key, {'date': key, 'messages': 0, 'tokens': 0, 'users': set()})
            entry['messages'] += 1
            hourly[local.hour]['messages'] += 1

        daily_users = (
            await db.execute(
                bounded(select(MessageRecord.created_at, MessageRecord.user_id), MessageRecord.created_at)
            )
        ).all()
        for stamp, user_id in daily_users:
            key = datetime.fromtimestamp(stamp, zone).strftime('%Y-%m-%d')
            daily.setdefault(key, {'date': key, 'messages': 0, 'tokens': 0, 'users': set()})['users'].add(user_id)

        series = [
            {'date': k, 'messages': v['messages'], 'tokens': v['tokens'], 'active_users': len(v['users'])}
            for k, v in sorted(daily.items())
        ]
        series = _fill_date_gaps(series)

        # ── Per-model split ──────────────────────────────────────────────
        model_rows = (
            await db.execute(
                bounded(
                    select(
                        UsageRecord.model_id,
                        func.count(),
                        func.sum(UsageRecord.total_tokens),
                    ).group_by(UsageRecord.model_id),
                    UsageRecord.created_at,
                )
            )
        ).all()
        models = sorted(
            [
                {'model_id': row[0] or 'unknown', 'messages': int(row[1] or 0), 'tokens': int(row[2] or 0)}
                for row in model_rows
            ],
            key=lambda e: e['tokens'],
            reverse=True,
        )

        total_tokens = sum(e['total_tokens'] for e in per_user)
        total_messages = sum(e['messages'] for e in per_user)

        return {
            'range': {'start': start, 'end': end, 'timezone': timezone_name},
            'totals': {
                'users': len(per_user),
                'messages': total_messages,
                'tokens': total_tokens,
                'input_tokens': sum(e['input_tokens'] for e in per_user),
                'output_tokens': sum(e['output_tokens'] for e in per_user),
                'tokens_per_user': round(total_tokens / len(per_user), 1) if per_user else 0,
                'tokens_per_message': round(total_tokens / total_messages, 1) if total_messages else 0,
                'messages_per_user': round(total_messages / len(per_user), 1) if per_user else 0,
            },
            'per_user': per_user,
            'user_token_distribution': {
                'summary': _summarize(user_token_values),
                'histogram': _histogram(user_token_values),
            },
            'message_token_distribution': {
                'summary': _summarize(message_token_values),
                'histogram': _histogram(message_token_values),
            },
            'daily': series,
            'hourly': hourly,
            'models': models,
        }


def _fill_date_gaps(series: list[dict]) -> list[dict]:
    """Insert zero rows for days with no activity so the chart's x-axis is even."""
    if len(series) < 2:
        return series
    filled = []
    current = datetime.strptime(series[0]['date'], '%Y-%m-%d')
    last = datetime.strptime(series[-1]['date'], '%Y-%m-%d')
    by_date = {entry['date']: entry for entry in series}
    while current <= last:
        key = current.strftime('%Y-%m-%d')
        filled.append(by_date.get(key, {'date': key, 'messages': 0, 'tokens': 0, 'active_users': 0}))
        current += timedelta(days=1)
        if len(filled) > 400:  # a study should never be this long; guard anyway
            break
    return filled


def _empty_overview(timezone_name: str, start: Optional[int], end: Optional[int]) -> dict:
    return {
        'range': {'start': start, 'end': end, 'timezone': timezone_name},
        'totals': {
            'users': 0, 'messages': 0, 'tokens': 0, 'input_tokens': 0, 'output_tokens': 0,
            'tokens_per_user': 0, 'tokens_per_message': 0, 'messages_per_user': 0,
        },
        'per_user': [],
        'user_token_distribution': {'summary': _summarize([]), 'histogram': []},
        'message_token_distribution': {'summary': _summarize([]), 'histogram': []},
        'daily': [],
        'hourly': [{'hour': h, 'messages': 0, 'tokens': 0} for h in range(24)],
        'models': [],
    }


async def case_study_report(case_study_id: str, db: Optional[AsyncSession] = None) -> dict:
    """Arm-by-arm comparison plus the intervention funnel."""
    async with get_weblab_db(db) as db:
        study = await db.get(CaseStudy, case_study_id)
        if not study:
            return {}

        arms = {}
        for kind in ('control', 'treatment'):
            overview = await usage_overview(
                case_study_id=case_study_id,
                group_kind=kind,
                timezone_name=study.timezone or 'America/New_York',
                db=db,
            )
            arms[kind] = {
                'users': overview['totals']['users'],
                'messages': overview['totals']['messages'],
                'tokens': overview['totals']['tokens'],
                'tokens_per_user': overview['totals']['tokens_per_user'],
                'messages_per_user': overview['totals']['messages_per_user'],
                'token_summary': overview['user_token_distribution']['summary'],
                'histogram': overview['user_token_distribution']['histogram'],
                'daily': overview['daily'],
            }

        decisions = (
            await db.execute(
                select(Intervention.decision, func.count())
                .where(Intervention.case_study_id == case_study_id)
                .group_by(Intervention.decision)
            )
        ).all()
        funnel = {row[0]: int(row[1]) for row in decisions}
        shown = sum(funnel.values())
        accepted = funnel.get('accepted', 0)

        response_seconds = (
            await db.execute(
                select(func.avg(Intervention.response_seconds)).where(
                    Intervention.case_study_id == case_study_id, Intervention.response_seconds.isnot(None)
                )
            )
        ).scalar()

        postponement_rows = (
            await db.execute(
                select(
                    Postponement.status,
                    func.count(),
                    func.avg(cast(Postponement.ends_at - Postponement.started_at, Float)),
                )
                .where(Postponement.case_study_id == case_study_id)
                .group_by(Postponement.status)
            )
        ).all()
        postponements = {
            row[0]: {'count': int(row[1] or 0), 'avg_seconds': round(float(row[2] or 0), 1)}
            for row in postponement_rows
        }

        honoured = (
            await db.execute(
                select(func.count()).select_from(Postponement).where(
                    Postponement.case_study_id == case_study_id, Postponement.honoured.is_(True)
                )
            )
        ).scalar() or 0

        by_window = (
            await db.execute(
                select(
                    Intervention.demand_window_label,
                    func.count(),
                    func.sum(case((Intervention.decision == 'accepted', 1), else_=0)),
                )
                .where(Intervention.case_study_id == case_study_id)
                .group_by(Intervention.demand_window_label)
            )
        ).all()

        membership_changes = (
            await db.execute(
                select(func.count()).select_from(Membership).where(
                    Membership.case_study_id == case_study_id, Membership.reason != 'enrolled'
                )
            )
        ).scalar() or 0

        return {
            'case_study': {
                'id': study.id,
                'name': study.name,
                'status': study.status,
                'timezone': study.timezone,
                'starts_at': study.starts_at,
                'ends_at': study.ends_at,
                'intervention_starts_at': study.intervention_starts_at,
                'intervention_ends_at': study.intervention_ends_at,
                'postpone_mode': study.postpone_mode,
                'postpone_minutes': study.postpone_minutes,
            },
            'arms': arms,
            'interventions': {
                'shown': shown,
                'accepted': accepted,
                'declined': funnel.get('declined', 0),
                'dismissed': funnel.get('dismissed', 0),
                'pending': funnel.get('pending', 0),
                'acceptance_rate': round(accepted / shown, 4) if shown else 0,
                'avg_response_seconds': round(float(response_seconds or 0), 1),
                'by_window': [
                    {
                        'label': row[0] or 'Unlabelled window',
                        'shown': int(row[1] or 0),
                        'accepted': int(row[2] or 0),
                        'acceptance_rate': round(int(row[2] or 0) / int(row[1]), 4) if row[1] else 0,
                    }
                    for row in by_window
                ],
            },
            'postponements': {
                'by_status': postponements,
                'honoured': int(honoured),
                'total': sum(entry['count'] for entry in postponements.values()),
            },
            'membership_changes': int(membership_changes),
        }
