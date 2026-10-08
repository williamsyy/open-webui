<script>
	import { onDestroy } from 'svelte';
	import { fade, scale } from 'svelte/transition';

	import { checkIntervention, recordDecision, releasePostponement } from '$lib/apis/weblab';

	// Gates message sending for participants in a running Web Lab case study.
	//
	// `gate()` resolves once the message may go out. Accepting a postponement
	// simply makes it resolve later — the pending message is never dropped, and
	// any path that ends the popup (decline, dismiss, override, or an error)
	// resolves it immediately. That way a study can never cost someone a message.

	let visible = false;
	let mode = 'prompt'; // prompt | waiting
	let payload = null;
	let remaining = 0;
	let ticker = null;
	let resolveGate = null;
	let busy = false;

	const clearTicker = () => {
		if (ticker) {
			clearInterval(ticker);
			ticker = null;
		}
	};

	const finish = () => {
		clearTicker();
		visible = false;
		payload = null;
		const resolve = resolveGate;
		resolveGate = null;
		resolve?.();
	};

	const startCountdown = (endsAt) => {
		clearTicker();
		const tick = () => {
			remaining = Math.max(0, Math.round(endsAt - Date.now() / 1000));
			if (remaining <= 0) {
				// The wait is over: close it out and let the held message through.
				releasePostponement(localStorage.token, 'elapsed', payload?.case_study_id).catch(() => {});
				finish();
			}
		};
		tick();
		ticker = setInterval(tick, 1000);
	};

	export const gate = async (chatId) => {
		// Never let a study failure block a message.
		let result;
		try {
			result = await checkIntervention(localStorage.token, chatId);
		} catch (error) {
			console.error('Web Lab check failed', error);
			return;
		}

		if (!result || result.action === 'none') return;

		payload = result;

		if (result.action === 'waiting') {
			mode = 'waiting';
			visible = true;
			startCountdown(result.ends_at);
			return new Promise((resolve) => (resolveGate = resolve));
		}

		mode = 'prompt';
		visible = true;
		remaining = result.postpone_seconds ?? 0;
		return new Promise((resolve) => (resolveGate = resolve));
	};

	const accept = async () => {
		busy = true;
		try {
			const result = await recordDecision(localStorage.token, payload.intervention_id, 'accepted');
			mode = 'waiting';
			startCountdown(result.ends_at ?? Date.now() / 1000 + (payload.postpone_seconds ?? 0));
		} catch (error) {
			console.error('Web Lab decision failed', error);
			finish();
		}
		busy = false;
	};

	const decline = async () => {
		busy = true;
		try {
			await recordDecision(localStorage.token, payload.intervention_id, 'declined');
		} catch (error) {
			console.error('Web Lab decision failed', error);
		}
		busy = false;
		finish();
	};

	const sendAnyway = async () => {
		busy = true;
		try {
			await releasePostponement(localStorage.token, 'override', payload?.case_study_id);
		} catch (error) {
			console.error('Web Lab release failed', error);
		}
		busy = false;
		finish();
	};

	onDestroy(() => {
		// Left the page with the question still on screen: record that it was
		// never answered, rather than leaving the row pending forever.
		if (mode === 'prompt' && payload?.intervention_id) {
			recordDecision(localStorage.token, payload.intervention_id, 'dismissed').catch(() => {});
		}
		clearTicker();
		resolveGate?.();
	});

	const clock = (seconds) => {
		const m = Math.floor(seconds / 60);
		const s = seconds % 60;
		return `${m}:${String(s).padStart(2, '0')}`;
	};

	$: totalSeconds = payload?.postpone_seconds ?? payload?.remaining_seconds ?? 1;
	$: progress = mode === 'waiting' ? 1 - remaining / Math.max(totalSeconds, 1) : 0;
</script>

{#if visible && payload}
	<div
		class="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/40 backdrop-blur-[2px]"
		transition:fade={{ duration: 120 }}
	>
		<div
			class="w-full max-w-md rounded-2xl bg-white dark:bg-gray-900 shadow-xl border border-gray-100 dark:border-gray-850 p-6"
			transition:scale={{ duration: 140, start: 0.97 }}
		>
			{#if mode === 'prompt'}
				<div class="flex items-start gap-3">
					<div
						class="shrink-0 w-9 h-9 rounded-full bg-amber-100 dark:bg-amber-500/15 flex items-center justify-center"
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke-width="2"
							stroke="currentColor"
							class="w-5 h-5 text-amber-600 dark:text-amber-400"
						>
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
							/>
						</svg>
					</div>
					<div class="min-w-0">
						<div class="font-medium">{payload.title}</div>
						<div class="text-sm text-gray-600 dark:text-gray-400 mt-1.5 leading-relaxed">
							{payload.body}
						</div>
						<div class="text-xs text-gray-400 mt-2">
							{payload.postpone_mode === 'window_end'
								? `That would be about ${clock(payload.postpone_seconds)} — until the current busy period ends.`
								: `That would be ${clock(payload.postpone_seconds)}.`}
						</div>
					</div>
				</div>

				<div class="flex flex-col gap-2 mt-5">
					<button
						class="w-full text-sm px-4 py-2.5 rounded-xl bg-black dark:bg-white text-white dark:text-black font-medium disabled:opacity-50"
						disabled={busy}
						on:click={accept}
					>
						{payload.accept_label}
					</button>
					<button
						class="w-full text-sm px-4 py-2.5 rounded-xl bg-gray-50 dark:bg-gray-850 disabled:opacity-50"
						disabled={busy}
						on:click={decline}
					>
						{payload.decline_label}
					</button>
				</div>
			{:else}
				<div class="text-center">
					<div class="text-3xl font-light tabular-nums">{clock(remaining)}</div>
					<div class="text-sm text-gray-600 dark:text-gray-400 mt-2 leading-relaxed">
						{payload.body}
					</div>

					<div class="h-1.5 rounded-full bg-gray-100 dark:bg-gray-850 overflow-hidden mt-4">
						<div
							class="h-full bg-blue-500 rounded-full transition-all duration-1000 ease-linear"
							style="width: {Math.min(Math.max(progress, 0), 1) * 100}%"
						></div>
					</div>

					<div class="text-xs text-gray-400 mt-3">
						Your message is held and will send on its own.
					</div>

					{#if payload.allow_override}
						<button
							class="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 mt-4 disabled:opacity-50"
							disabled={busy}
							on:click={sendAnyway}
						>
							Send it now instead
						</button>
					{/if}
				</div>
			{/if}

		</div>
	</div>
{/if}
