<script>
	import { getContext, onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { getCaseStudies } from '$lib/apis/weblab';
	import CaseStudies from './WebLab/CaseStudies.svelte';
	import DataStore from './WebLab/DataStore.svelte';
	import DemandWindows from './WebLab/DemandWindows.svelte';
	import Participants from './WebLab/Participants.svelte';
	import Results from './WebLab/Results.svelte';
	import Usage from './WebLab/Usage.svelte';

	export let token = '';

	const i18n = getContext('i18n');

	let loaded = false;
	let caseStudies = [];
	let selectedId = '';
	let tab = 'usage';

	// The study-scoped tabs only make sense once a case study is picked.
	const SCOPED_TABS = ['participants', 'windows', 'results'];

	const load = async () => {
		try {
			caseStudies = await getCaseStudies(token);
			if (!selectedId) {
				const running = caseStudies.find((s) => s.status === 'running');
				selectedId = running?.id ?? caseStudies[0]?.id ?? '';
			}
		} catch (error) {
			toast.error(`${error}`);
		}
		loaded = true;
	};

	onMount(load);

	$: selected = caseStudies.find((s) => s.id === selectedId) ?? null;

	const TABS = [
		['usage', 'Usage'],
		['studies', 'Case studies'],
		['participants', 'Participants'],
		['windows', 'Demand windows'],
		['results', 'Results'],
		['data', 'Data']
	];

	const PHASE_HINT = {
		baseline: 'Collecting usage. No popups are shown yet.',
		treatment: 'Treatment arm sees the high-demand popup inside a loaded window.',
		scheduled: 'Has not started yet.',
		ended: 'Finished — the data is still here.',
		draft: 'Not running.',
		observation: 'Running, with no treatment period set.',
		'post-treatment': 'Treatment period has closed; still collecting usage.',
		archived: 'Archived.'
	};
</script>

<div class="flex flex-col w-full min-h-full">
	<div class="flex items-center justify-between gap-3 mb-1">
		<div class="text-lg font-medium">Web Lab</div>
		{#if selected && ['participants', 'windows', 'results'].includes(tab)}
			<select
				bind:value={selectedId}
				class="text-sm rounded-lg px-2.5 py-1.5 bg-gray-50 dark:bg-gray-850 outline-none max-w-[280px]"
			>
				{#each caseStudies as study}
					<option value={study.id}>{study.name}</option>
				{/each}
			</select>
		{/if}
	</div>

	<div class="text-xs text-gray-400 mb-4">
		Chatbot usage monitoring and high-demand postponement studies. Everything is recorded in a
		separate, recoverable study database.
	</div>

	<div class="flex gap-1 mb-4 overflow-x-auto scrollbar-none">
		{#each TABS as [key, label]}
			<button
				class="text-sm px-3 py-1.5 rounded-lg whitespace-nowrap transition {tab === key
					? 'bg-gray-100 dark:bg-gray-850 font-medium'
					: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
				on:click={() => (tab = key)}
			>
				{label}
			</button>
		{/each}
	</div>

	{#if !loaded}
		<div class="py-20 text-center text-sm text-gray-400">Loading…</div>
	{:else if SCOPED_TABS.includes(tab) && !selectedId}
		<div
			class="rounded-xl border border-dashed border-gray-200 dark:border-gray-800 py-16 text-center"
		>
			<div class="text-sm text-gray-500">Create a case study first.</div>
			<button class="text-sm text-blue-500 hover:underline mt-1" on:click={() => (tab = 'studies')}>
				Go to case studies
			</button>
		</div>
	{:else}
		{#if selected && SCOPED_TABS.includes(tab)}
			<div
				class="rounded-lg bg-gray-50 dark:bg-gray-850 px-3 py-2 mb-4 text-xs text-gray-500 flex flex-wrap items-center gap-2"
			>
				<span class="font-medium text-gray-700 dark:text-gray-300">{selected.phase}</span>
				<span>· {PHASE_HINT[selected.phase] ?? ''}</span>
				<span class="ml-auto">
					{selected.postpone_mode === 'window_end'
						? 'Postpone until the window ends'
						: `Postpone ${selected.postpone_minutes} min`}
				</span>
			</div>
		{/if}

		{#if tab === 'usage'}
			<Usage {token} {caseStudies} />
		{:else if tab === 'studies'}
			<CaseStudies
				{token}
				{caseStudies}
				bind:selectedId
				on:changed={load}
				on:select={(e) => {
					selectedId = e.detail;
					tab = 'participants';
				}}
			/>
		{:else if tab === 'participants'}
			<Participants {token} caseStudyId={selectedId} />
		{:else if tab === 'windows'}
			<DemandWindows {token} caseStudyId={selectedId} timezone={selected?.timezone ?? ''} />
		{:else if tab === 'results'}
			<Results {token} caseStudyId={selectedId} />
		{:else if tab === 'data'}
			<DataStore {token} />
		{/if}
	{/if}
</div>
