<script>
	import { createEventDispatcher, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		archiveCaseStudy,
		createCaseStudy,
		getCaseStudy,
		updateCaseStudy
	} from '$lib/apis/weblab';
	import { formatStamp, fromLocalInput, toLocalInput } from './datetime';

	export let token = '';
	export let caseStudies = [];
	export let selectedId = '';

	const dispatch = createEventDispatcher();

	let editing = null;
	let saving = false;

	const PHASE_TONE = {
		baseline: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
		treatment: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
		scheduled: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
		ended: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500',
		draft: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
		archived: 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500'
	};

	const openEditor = async (id) => {
		try {
			const study = await getCaseStudy(token, id);
			editing = {
				...study,
				_starts_at: toLocalInput(study.starts_at),
				_ends_at: toLocalInput(study.ends_at),
				_intervention_starts_at: toLocalInput(study.intervention_starts_at),
				_intervention_ends_at: toLocalInput(study.intervention_ends_at)
			};
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const startNew = () => {
		const now = Math.floor(Date.now() / 1000);
		editing = {
			id: null,
			name: '',
			description: '',
			status: 'draft',
			timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'America/New_York',
			postpone_mode: 'fixed',
			postpone_minutes: 5,
			postpone_min_minutes: 1,
			postpone_max_minutes: null,
			reprompt_cooldown_minutes: 10,
			require_demand_window: true,
			trigger_probability: 1,
			allow_override: true,
			prompt_title: 'The system is in high demand',
			prompt_body:
				'We are seeing unusually heavy usage right now. Are you happy to postpone this response for a few minutes? Your message will be sent automatically when the wait is over.',
			accept_label: 'Yes, postpone my response',
			decline_label: 'No, send it now',
			waiting_body: 'Thanks for waiting — your message will go through when the timer ends.',
			_starts_at: toLocalInput(now),
			_ends_at: toLocalInput(now + 14 * 86400),
			_intervention_starts_at: toLocalInput(now + 7 * 86400),
			_intervention_ends_at: toLocalInput(now + 14 * 86400)
		};
	};

	const save = async () => {
		if (!editing.name?.trim()) {
			toast.error('Give the case study a name.');
			return;
		}
		saving = true;
		const payload = {
			name: editing.name,
			description: editing.description,
			status: editing.status,
			timezone: editing.timezone,
			starts_at: fromLocalInput(editing._starts_at),
			ends_at: fromLocalInput(editing._ends_at),
			intervention_starts_at: fromLocalInput(editing._intervention_starts_at),
			intervention_ends_at: fromLocalInput(editing._intervention_ends_at),
			postpone_mode: editing.postpone_mode,
			postpone_minutes: Number(editing.postpone_minutes),
			postpone_min_minutes: Number(editing.postpone_min_minutes),
			postpone_max_minutes: editing.postpone_max_minutes
				? Number(editing.postpone_max_minutes)
				: null,
			reprompt_cooldown_minutes: Number(editing.reprompt_cooldown_minutes),
			require_demand_window: editing.require_demand_window,
			trigger_probability: Number(editing.trigger_probability),
			allow_override: editing.allow_override,
			prompt_title: editing.prompt_title,
			prompt_body: editing.prompt_body,
			accept_label: editing.accept_label,
			decline_label: editing.decline_label,
			waiting_body: editing.waiting_body
		};

		try {
			if (editing.id) {
				await updateCaseStudy(token, editing.id, payload);
				toast.success('Case study updated.');
			} else {
				const created = await createCaseStudy(token, payload);
				toast.success('Case study created.');
				selectedId = created.id;
			}
			editing = null;
			dispatch('changed');
		} catch (error) {
			toast.error(`${error}`);
		}
		saving = false;
	};

	const archive = async (study) => {
		if (!confirm(`Archive "${study.name}"? Its data is kept — it just stops running.`)) return;
		try {
			await archiveCaseStudy(token, study.id);
			toast.success('Case study archived.');
			dispatch('changed');
		} catch (error) {
			toast.error(`${error}`);
		}
	};
</script>

{#if editing}
	<div class="flex flex-col gap-5 max-w-3xl">
		<div class="flex items-center gap-3">
			<button class="text-sm text-gray-500 hover:underline" on:click={() => (editing = null)}>
				← Back
			</button>
			<div class="text-base font-medium">
				{editing.id ? 'Edit case study' : 'New case study'}
			</div>
		</div>

		<!-- Identity -->
		<section class="flex flex-col gap-3">
			<div>
				<label class="text-xs text-gray-500" for="cs-name">Name</label>
				<input
					id="cs-name"
					bind:value={editing.name}
					placeholder="Fall 2026 high-demand postponement"
					class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
				/>
			</div>
			<div>
				<label class="text-xs text-gray-500" for="cs-desc">Description</label>
				<textarea
					id="cs-desc"
					bind:value={editing.description}
					rows="2"
					class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none resize-none"
				></textarea>
			</div>
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="text-xs text-gray-500" for="cs-status">Status</label>
					<select
						id="cs-status"
						bind:value={editing.status}
						class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					>
						<option value="draft">Draft — nothing runs</option>
						<option value="running">Running</option>
						<option value="completed">Completed</option>
						<option value="archived">Archived</option>
					</select>
				</div>
				<div>
					<label class="text-xs text-gray-500" for="cs-tz">Timezone</label>
					<input
						id="cs-tz"
						bind:value={editing.timezone}
						class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
				</div>
			</div>
		</section>

		<!-- Phases -->
		<section class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
			<div class="text-sm font-medium">Phases</div>
			<div class="text-xs text-gray-400 mt-0.5 mb-3">
				Usage is collected for every participant from the day they are enrolled. Popups only
				start when the treatment period opens — that is your week 1 / week 2 split.
			</div>
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="text-xs text-gray-500" for="cs-start">Study starts</label>
					<input
						id="cs-start"
						type="datetime-local"
						bind:value={editing._starts_at}
						class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-500" for="cs-end">Study ends</label>
					<input
						id="cs-end"
						type="datetime-local"
						bind:value={editing._ends_at}
						class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-500" for="cs-tstart">Treatment starts (week 2)</label>
					<input
						id="cs-tstart"
						type="datetime-local"
						bind:value={editing._intervention_starts_at}
						class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
				</div>
				<div>
					<label class="text-xs text-gray-500" for="cs-tend">Treatment ends</label>
					<input
						id="cs-tend"
						type="datetime-local"
						bind:value={editing._intervention_ends_at}
						class="w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
				</div>
			</div>
		</section>

		<!-- Postponement -->
		<section class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
			<div class="text-sm font-medium">How long is the postponement?</div>
			<div class="text-xs text-gray-400 mt-0.5 mb-3">
				This is the choice you make per case study.
			</div>

			<div class="flex flex-col gap-2">
				<label
					class="flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition {editing.postpone_mode ===
					'fixed'
						? 'border-blue-500 bg-blue-50/50 dark:bg-blue-500/5'
						: 'border-gray-100 dark:border-gray-850'}"
				>
					<input
						type="radio"
						bind:group={editing.postpone_mode}
						value="fixed"
						class="mt-0.5"
					/>
					<div class="min-w-0">
						<div class="text-sm font-medium">A fixed amount of time</div>
						<div class="text-xs text-gray-500 mt-0.5">
							Every accepted postponement lasts the same number of minutes, whenever it happens.
						</div>
						{#if editing.postpone_mode === 'fixed'}
							<div class="flex items-center gap-2 mt-2">
								<input
									type="number"
									min="0.5"
									step="0.5"
									bind:value={editing.postpone_minutes}
									class="w-24 text-sm rounded-lg px-2 py-1.5 bg-white dark:bg-gray-850 outline-none"
								/>
								<span class="text-xs text-gray-500">minutes</span>
							</div>
						{/if}
					</div>
				</label>

				<label
					class="flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition {editing.postpone_mode ===
					'window_end'
						? 'border-blue-500 bg-blue-50/50 dark:bg-blue-500/5'
						: 'border-gray-100 dark:border-gray-850'}"
				>
					<input
						type="radio"
						bind:group={editing.postpone_mode}
						value="window_end"
						class="mt-0.5"
					/>
					<div class="min-w-0">
						<div class="text-sm font-medium">Until the high-demand window ends</div>
						<div class="text-xs text-gray-500 mt-0.5">
							The wait runs to the end of whichever window from your CSV is in force. Someone
							asked early in a peak waits longer than someone asked near its close.
						</div>
						{#if editing.postpone_mode === 'window_end'}
							<div class="flex flex-wrap items-center gap-2 mt-2">
								<span class="text-xs text-gray-500">but never shorter than</span>
								<input
									type="number"
									min="0"
									step="0.5"
									bind:value={editing.postpone_min_minutes}
									class="w-20 text-sm rounded-lg px-2 py-1.5 bg-white dark:bg-gray-850 outline-none"
								/>
								<span class="text-xs text-gray-500">min, nor longer than</span>
								<input
									type="number"
									min="0"
									step="1"
									placeholder="no cap"
									bind:value={editing.postpone_max_minutes}
									class="w-24 text-sm rounded-lg px-2 py-1.5 bg-white dark:bg-gray-850 outline-none"
								/>
								<span class="text-xs text-gray-500">min</span>
							</div>
							<div class="text-[11px] text-gray-400 mt-1.5">
								If no window happens to be open, the fixed time above is used instead.
							</div>
						{/if}
					</div>
				</label>
			</div>
		</section>

		<!-- Triggering -->
		<section class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
			<div class="text-sm font-medium mb-3">When to ask</div>
			<div class="flex flex-col gap-3">
				<label class="flex items-center gap-2.5 text-sm">
					<input type="checkbox" bind:checked={editing.require_demand_window} />
					<span>Only ask inside a high-demand window from the CSV</span>
				</label>
				<label class="flex items-center gap-2.5 text-sm">
					<input type="checkbox" bind:checked={editing.allow_override} />
					<span>Let people send anyway while they are waiting</span>
				</label>
				<div class="grid grid-cols-2 gap-3">
					<div>
						<label class="text-xs text-gray-500" for="cs-cool">
							Don't re-ask the same person within
						</label>
						<div class="flex items-center gap-2 mt-1">
							<input
								id="cs-cool"
								type="number"
								min="0"
								step="1"
								bind:value={editing.reprompt_cooldown_minutes}
								class="w-24 text-sm rounded-lg px-2 py-1.5 bg-gray-50 dark:bg-gray-850 outline-none"
							/>
							<span class="text-xs text-gray-500">minutes</span>
						</div>
					</div>
					<div>
						<label class="text-xs text-gray-500" for="cs-prob">
							Ask on this share of eligible messages
						</label>
						<div class="flex items-center gap-2 mt-1">
							<input
								id="cs-prob"
								type="number"
								min="0"
								max="1"
								step="0.05"
								bind:value={editing.trigger_probability}
								class="w-24 text-sm rounded-lg px-2 py-1.5 bg-gray-50 dark:bg-gray-850 outline-none"
							/>
							<span class="text-xs text-gray-500">1 = always</span>
						</div>
					</div>
				</div>
			</div>
		</section>

		<!-- Copy -->
		<section class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
			<div class="text-sm font-medium mb-3">What the popup says</div>
			<div class="flex flex-col gap-3">
				<input
					bind:value={editing.prompt_title}
					placeholder="Title"
					class="w-full text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
				/>
				<textarea
					bind:value={editing.prompt_body}
					rows="3"
					placeholder="Body"
					class="w-full text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none resize-none"
				></textarea>
				<div class="grid grid-cols-2 gap-3">
					<input
						bind:value={editing.accept_label}
						placeholder="Accept button"
						class="w-full text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
					<input
						bind:value={editing.decline_label}
						placeholder="Decline button"
						class="w-full text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
					/>
				</div>
				<textarea
					bind:value={editing.waiting_body}
					rows="2"
					placeholder="Shown while waiting"
					class="w-full text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none resize-none"
				></textarea>
			</div>
		</section>

		<div class="flex gap-2">
			<button
				class="text-sm px-4 py-2 rounded-lg bg-black dark:bg-white text-white dark:text-black font-medium disabled:opacity-50"
				disabled={saving}
				on:click={save}
			>
				{saving ? 'Saving…' : editing.id ? 'Save changes' : 'Create case study'}
			</button>
			<button
				class="text-sm px-4 py-2 rounded-lg bg-gray-50 dark:bg-gray-850"
				on:click={() => (editing = null)}
			>
				Cancel
			</button>
		</div>
	</div>
{:else}
	<div class="flex flex-col gap-3">
		<div class="flex items-center justify-between">
			<div class="text-sm text-gray-500">
				{caseStudies.length} case {caseStudies.length === 1 ? 'study' : 'studies'}
			</div>
			<button
				class="text-sm px-3 py-1.5 rounded-lg bg-black dark:bg-white text-white dark:text-black font-medium"
				on:click={startNew}
			>
				New case study
			</button>
		</div>

		<div class="flex flex-col gap-2">
			{#each caseStudies as study}
				<div
					class="rounded-xl border border-gray-100 dark:border-gray-850 p-4 flex items-start gap-4"
				>
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2 flex-wrap">
							<div class="font-medium truncate">{study.name}</div>
							<span
								class="text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wide {PHASE_TONE[
									study.phase
								] ?? PHASE_TONE.draft}"
							>
								{study.phase}
							</span>
						</div>
						{#if study.description}
							<div class="text-xs text-gray-500 mt-1 line-clamp-2">{study.description}</div>
						{/if}
						<div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400 mt-2">
							<span>{study.participant_count} participants</span>
							<span>{study.demand_window_count} demand windows</span>
							<span>
								Postpone: {study.postpone_mode === 'window_end'
									? 'until window ends'
									: `${study.postpone_minutes} min fixed`}
							</span>
							<span>Treatment from {formatStamp(study.intervention_starts_at)}</span>
						</div>
					</div>
					<div class="flex flex-col gap-1.5">
						<button
							class="text-xs px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850"
							on:click={() => openEditor(study.id)}
						>
							Settings
						</button>
						<button
							class="text-xs px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850"
							on:click={() => {
								selectedId = study.id;
								dispatch('select', study.id);
							}}
						>
							Open
						</button>
						{#if study.status !== 'archived'}
							<button
								class="text-xs px-3 py-1.5 rounded-lg text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10"
								on:click={() => archive(study)}
							>
								Archive
							</button>
						{/if}
					</div>
				</div>
			{:else}
				<div
					class="rounded-xl border border-dashed border-gray-200 dark:border-gray-800 py-16 text-center"
				>
					<div class="text-sm text-gray-500">No case studies yet.</div>
					<button class="text-sm text-blue-500 hover:underline mt-1" on:click={startNew}>
						Create the first one
					</button>
				</div>
			{/each}
		</div>
	</div>
{/if}
