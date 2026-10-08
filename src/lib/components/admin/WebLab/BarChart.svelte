<script>
	// Generic bar chart used for the token histogram and the hour-of-day profile.
	export let data = []; // [{ label, value, emphasis? }]
	export let height = 160;
	export let color = 'var(--weblab-accent, #4f8ef7)';
	export let valueFormat = (v) => v.toLocaleString();
	export let xLabelEvery = 1;

	$: max = Math.max(1, ...data.map((d) => d.value ?? 0));
	let hovered = null;
</script>

<div class="w-full">
	<div class="flex items-end gap-[2px] w-full" style="height: {height}px">
		{#each data as d, i}
			<div
				class="flex-1 min-w-[3px] flex items-end h-full group relative"
				role="presentation"
				on:mouseenter={() => (hovered = i)}
				on:mouseleave={() => (hovered = null)}
			>
				<div
					class="w-full rounded-t-[2px] transition-all"
					style="height: {((d.value ?? 0) / max) * 100}%; background: {d.emphasis
						? 'var(--weblab-accent-strong, #2563eb)'
						: color}; opacity: {hovered === null || hovered === i ? 1 : 0.45}; min-height: {(d.value ??
						0) > 0
						? '2px'
						: '0px'}"
				></div>

				{#if hovered === i}
					<div
						class="absolute bottom-full mb-1 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap rounded-md bg-gray-900 dark:bg-gray-800 text-white text-xs px-2 py-1 shadow-lg"
					>
						<div class="font-medium">{valueFormat(d.value ?? 0)}</div>
						<div class="opacity-70">{d.label}</div>
					</div>
				{/if}
			</div>
		{/each}
	</div>

	<div class="flex gap-[2px] w-full mt-1.5">
		{#each data as d, i}
			<div class="flex-1 min-w-[3px] text-[10px] text-gray-400 dark:text-gray-500 text-center truncate">
				{i % xLabelEvery === 0 ? d.shortLabel ?? d.label : ''}
			</div>
		{/each}
	</div>
</div>
