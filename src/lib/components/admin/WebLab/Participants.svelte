<script>
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		endParticipation,
		enrollParticipants,
		getCandidateUsers,
		getParticipantHistory,
		getParticipants,
		randomizeParticipants,
		setMembership
	} from '$lib/apis/weblab';
	import { formatDuration, formatStamp } from './datetime';

	export let token = '';
	export let caseStudyId = '';

	let loading = true;
	let participants = [];
	let selected = new Set();
	let showEnroll = false;
	let candidates = [];
	let candidateQuery = '';
	let candidateSelection = new Set();
	let historyFor = null;
	let history = null;

	const load = async () => {
		if (!caseStudyId) return;
		loading = true;
		try {
			participants = await getParticipants(token, caseStudyId);
			selected = new Set();
		} catch (error) {
			toast.error(`${error}`);
		}
		loading = false;
	};

	$: if (caseStudyId) load();

	const openEnroll = async () => {
		showEnroll = true;
		candidateSelection = new Set();
		try {
			candidates = await getCandidateUsers(token, caseStudyId, candidateQuery);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const searchCandidates = async () => {
		try {
			candidates = await getCandidateUsers(token, caseStudyId, candidateQuery);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const enroll = async () => {
		if (candidateSelection.size === 0) return;
		try {
			const result = await enrollParticipants(token, caseStudyId, {
				user_ids: [...candidateSelection],
				group_kind: 'control'
			});
			toast.success(
				`Enrolled ${result.enrolled}${result.reactivated ? `, reactivated ${result.reactivated}` : ''}${result.skipped ? `, ${result.skipped} already in` : ''}.`
			);
			showEnroll = false;
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const move = async (kind) => {
		if (selected.size === 0) return;
		const reason = prompt(
			`Why are these ${selected.size} participant(s) moving to ${kind}?`,
			kind === 'treatment' ? 'week 2 treatment cohort' : 'moved back to control'
		);
		if (reason === null) return;
		try {
			const result = await setMembership(token, caseStudyId, {
				user_ids: [...selected],
				group_kind: kind,
				reason
			});
			toast.success(`Moved ${result.moved} participant(s) to ${kind}.`);
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const randomize = async () => {
		const raw = prompt('What fraction should go to treatment? (0–1)', '0.5');
		if (raw === null) return;
		const fraction = Number(raw);
		if (Number.isNaN(fraction) || fraction < 0 || fraction > 1) {
			toast.error('Enter a number between 0 and 1.');
			return;
		}
		try {
			const result = await randomizeParticipants(token, caseStudyId, {
				treatment_fraction: fraction
			});
			toast.success(`${result.treatment} in treatment, ${result.control} in control.`);
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const removeParticipant = async (row) => {
		if (!confirm(`End ${row.user_name ?? row.user_id}'s participation? Their data is kept.`))
			return;
		try {
			await endParticipation(token, caseStudyId, row.user_id);
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const openHistory = async (row) => {
		historyFor = row;
		history = null;
		try {
			history = await getParticipantHistory(token, caseStudyId, row.user_id);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const toggle = (set, value) => {
		const next = new Set(set);
		next.has(value) ? next.delete(value) : next.add(value);
		return next;
	};

	const ARM_TONE = {
		treatment: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
		control: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
	};
</script>

{#if historyFor}
	<div class="flex flex-col gap-4">
		<div class="flex items-center gap-3">
			<button class="text-sm text-gray-500 hover:underline" on:click={() => (historyFor = null)}>
				← Back
			</button>
			<div class="text-base font-medium">
				{historyFor.user_name ?? historyFor.user_id}
			</div>
		</div>

		{#if !history}
			<div class="py-12 text-center text-sm text-gray-400">Loading…</div>
		{:else}
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
				<div class="text-sm font-medium mb-1">Arm history</div>
				<div class="text-xs text-gray-400 mb-3">
					Every change is kept, so any past moment can be reconstructed.
				</div>
				<div class="flex flex-col gap-2">
					{#each history.memberships as m}
						<div class="flex items-center gap-3 text-sm">
							<span
								class="text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wide {ARM_TONE[
									m.kind
								]}"
							>
								{m.kind}
							</span>
							<span class="text-gray-500">
								{formatStamp(m.effective_from)} → {m.effective_to
									? formatStamp(m.effective_to)
									: 'now'}
							</span>
							{#if m.reason}
								<span class="text-xs text-gray-400 truncate">{m.reason}</span>
							{/if}
						</div>
					{/each}
				</div>
			</div>

			<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
				<div class="px-4 py-3 border-b border-gray-100 dark:border-gray-850 text-sm font-medium">
					Popups shown ({history.interventions.length})
				</div>
				<div class="max-h-64 overflow-y-auto">
					<table class="w-full text-sm">
						<tbody>
							{#each history.interventions as i}
								<tr class="border-b border-gray-50 dark:border-gray-850/50">
									<td class="px-4 py-2 text-gray-500">{formatStamp(i.shown_at)}</td>
									<td class="px-4 py-2">{i.decision}</td>
									<td class="px-4 py-2 text-gray-500">{i.demand_window_label ?? '—'}</td>
									<td class="px-4 py-2 text-right text-gray-500">
										offered {formatDuration(i.offered_seconds)}
									</td>
									<td class="px-4 py-2 text-right text-gray-500">
										{i.response_seconds !== null ? `answered in ${formatDuration(i.response_seconds)}` : '—'}
									</td>
								</tr>
							{:else}
								<tr><td class="px-4 py-6 text-center text-gray-400">None yet.</td></tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>

			<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
				<div class="px-4 py-3 border-b border-gray-100 dark:border-gray-850 text-sm font-medium">
					Postponements ({history.postponements.length})
				</div>
				<div class="max-h-64 overflow-y-auto">
					<table class="w-full text-sm">
						<tbody>
							{#each history.postponements as p}
								<tr class="border-b border-gray-50 dark:border-gray-850/50">
									<td class="px-4 py-2 text-gray-500">{formatStamp(p.started_at)}</td>
									<td class="px-4 py-2">{formatDuration(p.ends_at - p.started_at)}</td>
									<td class="px-4 py-2 text-gray-500">{p.mode}</td>
									<td class="px-4 py-2">{p.status}</td>
									<td class="px-4 py-2 text-right text-gray-500">
										{p.honoured === true ? 'waited it out' : p.honoured === false ? 'sent early' : '—'}
									</td>
								</tr>
							{:else}
								<tr><td class="px-4 py-6 text-center text-gray-400">None yet.</td></tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	</div>
{:else if showEnroll}
	<div class="flex flex-col gap-3 max-w-2xl">
		<div class="flex items-center gap-3">
			<button class="text-sm text-gray-500 hover:underline" on:click={() => (showEnroll = false)}>
				← Back
			</button>
			<div class="text-base font-medium">Enrol users</div>
		</div>
		<div class="text-xs text-gray-400">
			Enrolling starts data collection for that user. Everyone begins in control; move them to
			treatment when the study calls for it.
		</div>

		<div class="flex gap-2">
			<input
				bind:value={candidateQuery}
				on:input={searchCandidates}
				placeholder="Search by name or email"
				class="flex-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
			/>
			<button
				class="text-sm px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-850"
				on:click={() =>
					(candidateSelection = new Set(
						candidates.filter((c) => !c.enrolled).map((c) => c.id)
					))}
			>
				Select all
			</button>
		</div>

		<div
			class="rounded-xl border border-gray-100 dark:border-gray-850 max-h-96 overflow-y-auto divide-y divide-gray-50 dark:divide-gray-850/50"
		>
			{#each candidates as candidate}
				<label
					class="flex items-center gap-3 px-4 py-2.5 {candidate.enrolled
						? 'opacity-50'
						: 'cursor-pointer'}"
				>
					<input
						type="checkbox"
						disabled={!!candidate.enrolled}
						checked={candidateSelection.has(candidate.id)}
						on:change={() => (candidateSelection = toggle(candidateSelection, candidate.id))}
					/>
					<div class="min-w-0 flex-1">
						<div class="text-sm truncate">{candidate.name}</div>
						<div class="text-xs text-gray-400 truncate">{candidate.email}</div>
					</div>
					{#if candidate.enrolled}
						<span class="text-xs text-gray-400">already {candidate.enrolled}</span>
					{:else}
						<span class="text-xs text-gray-400">{candidate.role}</span>
					{/if}
				</label>
			{:else}
				<div class="px-4 py-8 text-center text-sm text-gray-400">No users found.</div>
			{/each}
		</div>

		<button
			class="text-sm px-4 py-2 rounded-lg bg-black dark:bg-white text-white dark:text-black font-medium disabled:opacity-50 self-start"
			disabled={candidateSelection.size === 0}
			on:click={enroll}
		>
			Enrol {candidateSelection.size} user{candidateSelection.size === 1 ? '' : 's'}
		</button>
	</div>
{:else}
	<div class="flex flex-col gap-3">
		<div class="flex flex-wrap items-center gap-2">
			<button
				class="text-sm px-3 py-1.5 rounded-lg bg-black dark:bg-white text-white dark:text-black font-medium"
				on:click={openEnroll}
			>
				Enrol users
			</button>
			<button class="text-sm px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850" on:click={randomize}>
				Randomise arms
			</button>

			<div class="flex items-center gap-2 ml-auto">
				<span class="text-xs text-gray-400">
					{selected.size} selected
				</span>
				<button
					class="text-sm px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850 disabled:opacity-40"
					disabled={selected.size === 0}
					on:click={() => move('treatment')}
				>
					→ Treatment
				</button>
				<button
					class="text-sm px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850 disabled:opacity-40"
					disabled={selected.size === 0}
					on:click={() => move('control')}
				>
					→ Control
				</button>
			</div>
		</div>

		{#if loading}
			<div class="py-16 text-center text-sm text-gray-400">Loading participants…</div>
		{:else}
			<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead class="text-xs text-gray-500">
							<tr class="border-b border-gray-100 dark:border-gray-850">
								<th class="px-3 py-2 w-8">
									<input
										type="checkbox"
										checked={selected.size > 0 && selected.size === participants.length}
										on:change={(e) =>
											(selected = e.currentTarget.checked
												? new Set(participants.map((p) => p.user_id))
												: new Set())}
									/>
								</th>
								<th class="text-left font-medium px-3 py-2">Participant</th>
								<th class="text-left font-medium px-3 py-2">Arm</th>
								<th class="text-left font-medium px-3 py-2">Enrolled</th>
								<th class="text-right font-medium px-3 py-2">Changes</th>
								<th class="text-right font-medium px-3 py-2">Messages</th>
								<th class="text-right font-medium px-3 py-2">Tokens</th>
								<th class="text-right font-medium px-3 py-2">Popups</th>
								<th class="px-3 py-2"></th>
							</tr>
						</thead>
						<tbody>
							{#each participants as row}
								<tr
									class="border-b border-gray-50 dark:border-gray-850/50 {row.status === 'ended'
										? 'opacity-50'
										: ''}"
								>
									<td class="px-3 py-2">
										<input
											type="checkbox"
											checked={selected.has(row.user_id)}
											on:change={() => (selected = toggle(selected, row.user_id))}
										/>
									</td>
									<td class="px-3 py-2">
										<div class="truncate max-w-[200px]">{row.user_name ?? row.user_id}</div>
										{#if row.user_email}
											<div class="text-xs text-gray-400 truncate max-w-[200px]">
												{row.user_email}
											</div>
										{/if}
									</td>
									<td class="px-3 py-2">
										<span
											class="text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wide {ARM_TONE[
												row.group_kind
											] ?? ARM_TONE.control}"
										>
											{row.group_kind ?? 'none'}
										</span>
									</td>
									<td class="px-3 py-2 text-gray-500 text-xs">{formatStamp(row.joined_at)}</td>
									<td class="px-3 py-2 text-right tabular-nums text-gray-500">
										{row.membership_changes}
									</td>
									<td class="px-3 py-2 text-right tabular-nums">{row.total_messages.toLocaleString()}</td>
									<td class="px-3 py-2 text-right tabular-nums">{row.total_tokens.toLocaleString()}</td>
									<td class="px-3 py-2 text-right tabular-nums text-gray-500">
										{row.interventions_accepted}/{row.interventions_shown}
									</td>
									<td class="px-3 py-2 text-right whitespace-nowrap">
										<button
											class="text-xs text-blue-500 hover:underline"
											on:click={() => openHistory(row)}
										>
											History
										</button>
										{#if row.status === 'active'}
											<button
												class="text-xs text-gray-400 hover:text-red-500 ml-2"
												on:click={() => removeParticipant(row)}
											>
												End
											</button>
										{/if}
									</td>
								</tr>
							{:else}
								<tr>
									<td colspan="9" class="px-4 py-12 text-center text-gray-400">
										No participants yet — enrol some users to start collecting their usage.
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			</div>
		{/if}
	</div>
{/if}
