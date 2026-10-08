<script>
	// Daily trend with up to two series drawn on independent scales, so message
	// counts and token counts can share one chart without one flattening the other.
	export let data = []; // [{ date, ...metrics }]
	export let series = []; // [{ key, label, color }]
	export let height = 200;

	const PAD = { top: 12, right: 8, bottom: 22, left: 8 };
	const WIDTH = 1000;

	$: plotHeight = height - PAD.top - PAD.bottom;
	$: plotWidth = WIDTH - PAD.left - PAD.right;

	const pointsFor = (rows, key, h, w) => {
		if (rows.length === 0) return '';
		const values = rows.map((r) => r[key] ?? 0);
		const max = Math.max(1, ...values);
		const step = rows.length > 1 ? w / (rows.length - 1) : 0;
		return values
			.map((v, i) => `${PAD.left + i * step},${PAD.top + h - (v / max) * h}`)
			.join(' ');
	};

	let hovered = null;
	$: labelEvery = Math.max(1, Math.ceil(data.length / 8));
</script>

{#if data.length === 0}
	<div class="h-[{height}px] flex items-center justify-center text-sm text-gray-400">
		No activity recorded yet.
	</div>
{:else}
	<div class="relative w-full">
		<svg viewBox="0 0 {WIDTH} {height}" class="w-full" style="height: {height}px" preserveAspectRatio="none">
			{#each [0, 0.25, 0.5, 0.75, 1] as fraction}
				<line
					x1={PAD.left}
					x2={WIDTH - PAD.right}
					y1={PAD.top + plotHeight * fraction}
					y2={PAD.top + plotHeight * fraction}
					stroke="currentColor"
					class="text-gray-200 dark:text-gray-800"
					stroke-width="1"
					vector-effect="non-scaling-stroke"
				/>
			{/each}

			{#each series as s}
				<polyline
					points={pointsFor(data, s.key, plotHeight, plotWidth)}
					fill="none"
					stroke={s.color}
					stroke-width="2"
					vector-effect="non-scaling-stroke"
					stroke-linejoin="round"
					stroke-linecap="round"
				/>
			{/each}

			{#each data as d, i}
				<rect
					x={PAD.left + (data.length > 1 ? (plotWidth / (data.length - 1)) * i - plotWidth / (data.length - 1) / 2 : 0)}
					y={PAD.top}
					width={data.length > 1 ? plotWidth / (data.length - 1) : plotWidth}
					height={plotHeight}
					fill="transparent"
					role="presentation"
					on:mouseenter={() => (hovered = i)}
					on:mouseleave={() => (hovered = null)}
				/>
			{/each}

			{#if hovered !== null}
				<line
					x1={PAD.left + (data.length > 1 ? (plotWidth / (data.length - 1)) * hovered : 0)}
					x2={PAD.left + (data.length > 1 ? (plotWidth / (data.length - 1)) * hovered : 0)}
					y1={PAD.top}
					y2={PAD.top + plotHeight}
					stroke="currentColor"
					class="text-gray-400"
					stroke-width="1"
					vector-effect="non-scaling-stroke"
				/>
			{/if}
		</svg>

		{#if hovered !== null}
			<div
				class="absolute top-0 z-10 rounded-md bg-gray-900 dark:bg-gray-800 text-white text-xs px-2 py-1.5 shadow-lg pointer-events-none"
				style="left: {Math.min(Math.max((hovered / Math.max(data.length - 1, 1)) * 100, 4), 82)}%"
			>
				<div class="font-medium mb-0.5">{data[hovered].date}</div>
				{#each series as s}
					<div class="flex items-center gap-1.5">
						<span class="w-2 h-2 rounded-full" style="background: {s.color}"></span>
						<span class="opacity-75">{s.label}</span>
						<span class="font-medium ml-auto">{(data[hovered][s.key] ?? 0).toLocaleString()}</span>
					</div>
				{/each}
			</div>
		{/if}

		<div class="flex justify-between mt-1 text-[10px] text-gray-400 dark:text-gray-500">
			{#each data.filter((_, i) => i % labelEvery === 0) as d}
				<span>{d.date.slice(5)}</span>
			{/each}
		</div>

		<div class="flex gap-4 mt-2 text-xs">
			{#each series as s}
				<div class="flex items-center gap-1.5">
					<span class="w-2.5 h-0.5 rounded" style="background: {s.color}"></span>
					<span class="text-gray-500 dark:text-gray-400">{s.label}</span>
				</div>
			{/each}
		</div>
	</div>
{/if}
