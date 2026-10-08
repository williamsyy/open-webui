<script>
	export let label = '';
	export let value = '';
	export let hint = '';
	export let tone = 'default'; // default | accent | warn
</script>

<div
	class="rounded-xl border border-gray-100 dark:border-gray-850 px-4 py-3 bg-white dark:bg-gray-900 min-w-0"
>
	<div class="text-xs text-gray-500 dark:text-gray-400 truncate">{label}</div>
	<div
		class="text-xl font-medium mt-0.5 tabular-nums truncate {tone === 'accent'
			? 'text-blue-600 dark:text-blue-400'
			: tone === 'warn'
				? 'text-amber-600 dark:text-amber-400'
				: ''}"
	>
		{value}
	</div>
	{#if hint}
		<div class="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5 truncate">{hint}</div>
	{/if}
</div>
