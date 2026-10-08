<script>
	import { toast } from 'svelte-sonner';

	import { exportUrl, getCaseStudyReport, getInterventions, getStudyEvents } from '$lib/apis/weblab';
	import LineChart from './LineChart.svelte';
	import StatTile from './StatTile.svelte';
	import { formatDuration, formatStamp } from './datetime';

	export let token = '';
	export let caseStudyId = '';

	let loading = true;
	let report = null;
	let interventions = [];
	let events = [];
	let tab = 'summary';

	const load = async () => {
		if (!caseStudyId) return;
		loading = true;
		try {
			[report, interventions, events] = await Promise.all([
				getCaseStudyReport(token, caseStudyId),
				getInterventions(token, caseStudyId),
				getStudyEvents(token, caseStudyId)
			]);
		} catch (error) {
			toast.error(`${error}`);
		}
		loading = false;
	};

	$: if (caseStudyId) load();

	const number = (v) => (v ?? 0).toLocaleString();
	const percent = (v) => `${Math.round((v ?? 0) * 100)}%`;

	// Both arms on one axis, so a difference in usage is visible directly.
	$: comparison = (() => {
		if (!report) return [];
		const byDate = new Map();
		for (const kind of ['control', 'treatment']) {
			for (const row of report.arms[kind]?.daily ?? []) {
				const entry = byDate.get(row.date) ?? { date: row.date, control: 0, treatment: 0 };
				entry[kind] = row.tokens;
				byDate.set(row.date, entry);
			}
		}
		return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
	})();

	const DECISION_TONE = {
		accepted: 'text-emerald-600 dark:text-emerald-400',
		declined: 'text-red-500',
		dismissed: 'text-gray-400',
		pending: 'text-amber-500'
	};
</script>

{#if loading}
	<div class="py-16 text-center text-sm text-gray-400">Loading results…</div>
{:else if report}
	<div class="flex flex-col gap-4">
		<div class="flex items-center gap-1 text-sm">
			{#each [['summary', 'Summary'], ['popups', `Popups (${interventions.length})`], ['log', 'Audit log']] as [key, label]}
				<button
					class="px-3 py-1.5 rounded-lg transition {tab === key
						? 'bg-gray-100 dark:bg-gray-850 font-medium'
						: 'text-gray-500'}"
					on:click={() => (tab = key)}
				>
					{label}
				</button>
			{/each}
			<div class="ml-auto flex gap-2">
				<a
					href={exportUrl(caseStudyId, 'csv')}
					class="text-xs px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850"
				>
					Export CSV
				</a>
				<a
					href={exportUrl(caseStudyId, 'json')}
					class="text-xs px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850"
				>
					Export JSON
				</a>
			</div>
		</div>

		{#if tab === 'summary'}
			<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
				<StatTile label="Popups shown" value={number(report.interventions.shown)} />
				<StatTile
					label="Accepted"
					value={number(report.interventions.accepted)}
					hint={percent(report.interventions.acceptance_rate)}
					tone="accent"
				/>
				<StatTile label="Declined" value={number(report.interventions.declined)} />
				<StatTile
					label="Avg. time to answer"
					value={formatDuration(report.interventions.avg_response_seconds)}
				/>
				<StatTile
					label="Waits honoured"
					value="{number(report.postponements.honoured)}/{number(report.postponements.total)}"
					hint="waited the full time"
				/>
			</div>

			<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
				{#each ['control', 'treatment'] as kind}
					<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
						<div class="text-sm font-medium capitalize mb-3">{kind} arm</div>
						<div class="grid grid-cols-2 gap-3 text-sm">
							<div>
								<div class="text-xs text-gray-400">Participants</div>
								<div class="tabular-nums">{number(report.arms[kind].users)}</div>
							</div>
							<div>
								<div class="text-xs text-gray-400">Messages</div>
								<div class="tabular-nums">{number(report.arms[kind].messages)}</div>
							</div>
							<div>
								<div class="text-xs text-gray-400">Total tokens</div>
								<div class="tabular-nums">{number(report.arms[kind].tokens)}</div>
							</div>
							<div>
								<div class="text-xs text-gray-400">Tokens / user</div>
								<div class="tabular-nums">{number(report.arms[kind].tokens_per_user)}</div>
							</div>
							<div>
								<div class="text-xs text-gray-400">Median user</div>
								<div class="tabular-nums">{number(report.arms[kind].token_summary.median)}</div>
							</div>
							<div>
								<div class="text-xs text-gray-400">p95 user</div>
								<div class="tabular-nums">{number(report.arms[kind].token_summary.p95)}</div>
							</div>
						</div>
					</div>
				{/each}
			</div>

			<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
				<div class="text-sm font-medium mb-1">Tokens per day, by arm</div>
				<div class="text-xs text-gray-400 mb-3">
					The gap after the treatment period opens is the effect you are looking for.
				</div>
				<LineChart
					data={comparison}
					series={[
						{ key: 'control', label: 'Control', color: '#94a3b8' },
						{ key: 'treatment', label: 'Treatment', color: '#2563eb' }
					]}
				/>
			</div>

			{#if report.interventions.by_window?.length}
				<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
					<div class="text-sm font-medium mb-3">Acceptance by demand window</div>
					<div class="flex flex-col gap-2">
						{#each report.interventions.by_window as row}
							<div class="flex items-center gap-3 text-sm">
								<div class="w-48 truncate">{row.label}</div>
								<div class="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-850 overflow-hidden">
									<div
										class="h-full bg-emerald-500 rounded-full"
										style="width: {row.acceptance_rate * 100}%"
									></div>
								</div>
								<div class="w-24 text-right text-gray-500 tabular-nums">
									{row.accepted}/{row.shown} · {percent(row.acceptance_rate)}
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<div class="text-xs text-gray-400">
				{report.membership_changes} arm change{report.membership_changes === 1 ? '' : 's'} recorded
				during this study.
			</div>
		{:else if tab === 'popups'}
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
				<div class="max-h-[520px] overflow-y-auto">
					<table class="w-full text-sm">
						<thead class="text-xs text-gray-500 sticky top-0 bg-white dark:bg-gray-900">
							<tr class="border-b border-gray-100 dark:border-gray-850">
								<th class="text-left font-medium px-4 py-2">Shown</th>
								<th class="text-left font-medium px-4 py-2">Participant</th>
								<th class="text-left font-medium px-4 py-2">Arm</th>
								<th class="text-left font-medium px-4 py-2">Window</th>
								<th class="text-left font-medium px-4 py-2">Offered</th>
								<th class="text-left font-medium px-4 py-2">Decision</th>
								<th class="text-right font-medium px-4 py-2">Answered in</th>
							</tr>
						</thead>
						<tbody>
							{#each interventions as row}
								<tr class="border-b border-gray-50 dark:border-gray-850/50">
									<td class="px-4 py-2 text-gray-500 whitespace-nowrap">
										{formatStamp(row.shown_at)}
									</td>
									<td class="px-4 py-2 truncate max-w-[180px]">
										{row.user_name ?? row.user_id}
									</td>
									<td class="px-4 py-2 text-gray-500">{row.group_kind}</td>
									<td class="px-4 py-2 text-gray-500 truncate max-w-[160px]">
										{row.demand_window_label ?? '—'}
									</td>
									<td class="px-4 py-2 text-gray-500">
										{formatDuration(row.offered_seconds)}
										<span class="text-xs text-gray-400">({row.offered_mode})</span>
									</td>
									<td class="px-4 py-2 {DECISION_TONE[row.decision]}">{row.decision}</td>
									<td class="px-4 py-2 text-right text-gray-500">
										{row.response_seconds !== null ? formatDuration(row.response_seconds) : '—'}
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="7" class="px-4 py-12 text-center text-gray-400">
										No popups shown yet.
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{:else}
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
				<div class="max-h-[520px] overflow-y-auto divide-y divide-gray-50 dark:divide-gray-850/50">
					{#each events as event}
						<div class="px-4 py-2.5 flex items-start gap-3 text-sm">
							<div class="text-xs text-gray-400 w-32 shrink-0">{formatStamp(event.created_at)}</div>
							<div class="font-mono text-xs w-52 shrink-0 truncate">{event.type}</div>
							<div class="text-xs text-gray-500 truncate flex-1">
								{event.user_id ? `user ${event.user_id.slice(0, 8)} ` : ''}
								{event.data ? JSON.stringify(event.data) : ''}
							</div>
						</div>
					{:else}
						<div class="px-4 py-12 text-center text-gray-400">Nothing logged yet.</div>
					{/each}
				</div>
			</div>
		{/if}
	</div>
{/if}
