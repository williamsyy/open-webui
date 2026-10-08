<script>
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { getUsageOverview } from '$lib/apis/weblab';
	import BarChart from './BarChart.svelte';
	import LineChart from './LineChart.svelte';
	import StatTile from './StatTile.svelte';

	export let token = '';
	export let caseStudies = [];

	const i18n = getContext('i18n');

	let loading = true;
	let overview = null;

	let caseStudyId = '';
	let groupKind = '';
	let rangeDays = 30;

	const RANGES = [
		{ days: 7, label: '7 days' },
		{ days: 14, label: '14 days' },
		{ days: 30, label: '30 days' },
		{ days: 0, label: 'All time' }
	];

	const load = async () => {
		loading = true;
		const now = Math.floor(Date.now() / 1000);
		try {
			overview = await getUsageOverview(token, {
				start: rangeDays ? now - rangeDays * 86400 : undefined,
				end: rangeDays ? now : undefined,
				caseStudyId: caseStudyId || undefined,
				groupKind: groupKind || undefined,
				timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
			});
		} catch (error) {
			toast.error(`${error}`);
		}
		loading = false;
	};

	onMount(load);

	const number = (v) => (v ?? 0).toLocaleString();
	const compact = (v) =>
		Math.abs(v ?? 0) >= 1000
			? `${((v ?? 0) / 1000).toFixed((v ?? 0) >= 10000 ? 0 : 1)}k`
			: `${v ?? 0}`;

	$: histogram = (overview?.user_token_distribution?.histogram ?? []).map((b) => ({
		label: `${b.label} tokens`,
		shortLabel: compact(b.start),
		value: b.count
	}));

	$: hourly = (overview?.hourly ?? []).map((h) => ({
		label: `${String(h.hour).padStart(2, '0')}:00`,
		shortLabel: h.hour % 3 === 0 ? String(h.hour).padStart(2, '0') : '',
		value: h.messages
	}));

	$: summary = overview?.user_token_distribution?.summary ?? {};
	$: messageSummary = overview?.message_token_distribution?.summary ?? {};
</script>

<div class="flex flex-col gap-4">
	<!-- Filters -->
	<div class="flex flex-wrap items-center gap-2">
		<select
			bind:value={caseStudyId}
			on:change={load}
			class="text-sm rounded-lg px-2.5 py-1.5 bg-gray-50 dark:bg-gray-850 outline-none"
		>
			<option value="">All users on this server</option>
			{#each caseStudies as study}
				<option value={study.id}>{study.name}</option>
			{/each}
		</select>

		{#if caseStudyId}
			<select
				bind:value={groupKind}
				on:change={load}
				class="text-sm rounded-lg px-2.5 py-1.5 bg-gray-50 dark:bg-gray-850 outline-none"
			>
				<option value="">Both arms</option>
				<option value="control">Control only</option>
				<option value="treatment">Treatment only</option>
			</select>
		{/if}

		<div class="flex rounded-lg bg-gray-50 dark:bg-gray-850 p-0.5">
			{#each RANGES as range}
				<button
					class="text-xs px-2.5 py-1 rounded-md transition {rangeDays === range.days
						? 'bg-white dark:bg-gray-800 shadow-sm'
						: 'text-gray-500'}"
					on:click={() => {
						rangeDays = range.days;
						load();
					}}
				>
					{range.label}
				</button>
			{/each}
		</div>

		<button
			class="text-xs px-2.5 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850 ml-auto"
			on:click={load}
		>
			Refresh
		</button>
	</div>

	{#if loading}
		<div class="py-16 text-center text-sm text-gray-400">Loading usage…</div>
	{:else if overview}
		<!-- Headline numbers -->
		<div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
			<StatTile label="Users active" value={number(overview.totals.users)} />
			<StatTile label="Messages sent" value={number(overview.totals.messages)} />
			<StatTile label="Tokens used" value={number(overview.totals.tokens)} tone="accent" />
			<StatTile
				label="Tokens / user"
				value={number(overview.totals.tokens_per_user)}
				hint="mean across users"
			/>
			<StatTile
				label="Tokens / message"
				value={number(overview.totals.tokens_per_message)}
			/>
			<StatTile
				label="Messages / user"
				value={number(overview.totals.messages_per_user)}
			/>
		</div>

		<!-- Trend -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
			<div class="text-sm font-medium mb-1">Usage over time</div>
			<div class="text-xs text-gray-400 mb-3">
				Daily totals in {overview.range.timezone}
			</div>
			<LineChart
				data={overview.daily}
				series={[
					{ key: 'tokens', label: 'Tokens', color: '#2563eb' },
					{ key: 'messages', label: 'Messages', color: '#10b981' },
					{ key: 'active_users', label: 'Active users', color: '#f59e0b' }
				]}
			/>
		</div>

		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<!-- Token distribution -->
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
				<div class="text-sm font-medium mb-1">Token usage distribution</div>
				<div class="text-xs text-gray-400 mb-3">
					How many users fall in each total-token band
				</div>

				{#if histogram.length}
					<BarChart data={histogram} height={150} xLabelEvery={2} />
				{:else}
					<div class="h-[150px] flex items-center justify-center text-sm text-gray-400">
						No token usage recorded yet.
					</div>
				{/if}

				<div class="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-4 text-center">
					{#each [['Min', summary.min], ['p25', summary.p25], ['Median', summary.median], ['p75', summary.p75], ['p95', summary.p95], ['Max', summary.max]] as [label, value]}
						<div>
							<div class="text-[10px] text-gray-400 uppercase tracking-wide">{label}</div>
							<div class="text-sm tabular-nums">{number(value)}</div>
						</div>
					{/each}
				</div>
				<div class="text-[11px] text-gray-400 mt-2 text-center">
					Spread across {number(summary.count)} users — mean {number(summary.mean)}, σ {number(
						summary.stddev
					)}. Per message: median {number(messageSummary.median)}, p95 {number(messageSummary.p95)}.
				</div>
			</div>

			<!-- Hour of day -->
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
				<div class="text-sm font-medium mb-1">When people chat</div>
				<div class="text-xs text-gray-400 mb-3">
					Messages by hour of day — use this to pick high-demand windows
				</div>
				<BarChart data={hourly} height={150} color="#10b981" />
			</div>
		</div>

		<!-- Per-user table -->
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
			<div class="px-4 py-3 border-b border-gray-100 dark:border-gray-850">
				<div class="text-sm font-medium">Usage by user</div>
			</div>
			<div class="overflow-x-auto max-h-[420px] overflow-y-auto">
				<table class="w-full text-sm">
					<thead class="text-xs text-gray-500 sticky top-0 bg-white dark:bg-gray-900">
						<tr class="border-b border-gray-100 dark:border-gray-850">
							<th class="text-left font-medium px-4 py-2">User</th>
							<th class="text-right font-medium px-4 py-2">Messages</th>
							<th class="text-right font-medium px-4 py-2">Input</th>
							<th class="text-right font-medium px-4 py-2">Output</th>
							<th class="text-right font-medium px-4 py-2">Total tokens</th>
							<th class="text-left font-medium px-4 py-2 w-32">Share</th>
						</tr>
					</thead>
					<tbody>
						{#each overview.per_user as row}
							<tr class="border-b border-gray-50 dark:border-gray-850/50">
								<td class="px-4 py-2">
									<div class="truncate max-w-[220px]">{row.user_name ?? row.user_id}</div>
									{#if row.user_email}
										<div class="text-xs text-gray-400 truncate max-w-[220px]">{row.user_email}</div>
									{/if}
								</td>
								<td class="px-4 py-2 text-right tabular-nums">{number(row.messages)}</td>
								<td class="px-4 py-2 text-right tabular-nums text-gray-500"
									>{number(row.input_tokens)}</td
								>
								<td class="px-4 py-2 text-right tabular-nums text-gray-500"
									>{number(row.output_tokens)}</td
								>
								<td class="px-4 py-2 text-right tabular-nums font-medium"
									>{number(row.total_tokens)}</td
								>
								<td class="px-4 py-2">
									<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-850 overflow-hidden">
										<div
											class="h-full bg-blue-500 rounded-full"
											style="width: {overview.totals.tokens
												? (row.total_tokens / overview.totals.tokens) * 100
												: 0}%"
										></div>
									</div>
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="6" class="px-4 py-10 text-center text-gray-400">
									No usage recorded for this selection yet.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>

		{#if overview.models?.length}
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
				<div class="text-sm font-medium mb-3">By model</div>
				<div class="flex flex-col gap-2">
					{#each overview.models as model}
						<div class="flex items-center gap-3 text-sm">
							<div class="w-48 truncate">{model.model_id}</div>
							<div class="flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-850 overflow-hidden">
								<div
									class="h-full bg-blue-500 rounded-full"
									style="width: {overview.totals.tokens
										? (model.tokens / overview.totals.tokens) * 100
										: 0}%"
								></div>
							</div>
							<div class="w-24 text-right tabular-nums text-gray-500">
								{number(model.tokens)}
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>
