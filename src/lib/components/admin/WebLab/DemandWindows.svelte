<script>
	import { toast } from 'svelte-sonner';

	import {
		addDemandWindow,
		getDemandImports,
		getDemandWindows,
		importDemandCsv,
		previewDemandCsv,
		removeDemandWindow
	} from '$lib/apis/weblab';
	import { formatStamp, fromLocalInput, toLocalInput } from './datetime';

	export let token = '';
	export let caseStudyId = '';
	export let timezone = '';

	let loading = true;
	let windows = [];
	let imports = [];
	let preview = null;
	let pendingFile = null;
	let replaceExisting = false;
	let importing = false;
	let fileInput;

	let manualStart = '';
	let manualEnd = '';
	let manualLabel = '';

	const SAMPLE = `start,end,label
2026-09-07 09:00,2026-09-07 11:00,Monday morning peak
2026-09-07 14:00,2026-09-07 16:30,Monday afternoon peak
2026-09-08 09:00,2026-09-08 11:00,Tuesday morning peak`;

	const load = async () => {
		if (!caseStudyId) return;
		loading = true;
		try {
			[windows, imports] = await Promise.all([
				getDemandWindows(token, caseStudyId),
				getDemandImports(token, caseStudyId)
			]);
		} catch (error) {
			toast.error(`${error}`);
		}
		loading = false;
	};

	$: if (caseStudyId) load();

	const onFile = async (event) => {
		const file = event.currentTarget.files?.[0];
		if (!file) return;
		pendingFile = file;
		try {
			preview = await previewDemandCsv(token, caseStudyId, file, timezone || undefined);
		} catch (error) {
			toast.error(`${error}`);
			preview = null;
			pendingFile = null;
		}
	};

	const confirmImport = async () => {
		if (!pendingFile) return;
		importing = true;
		try {
			const result = await importDemandCsv(token, caseStudyId, pendingFile, {
				timezone: timezone || undefined,
				replace: replaceExisting
			});
			toast.success(
				`Imported ${result.imported} window${result.imported === 1 ? '' : 's'}${result.skipped ? `, skipped ${result.skipped}` : ''}.`
			);
			preview = null;
			pendingFile = null;
			if (fileInput) fileInput.value = '';
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
		importing = false;
	};

	const addManual = async () => {
		const starts_at = fromLocalInput(manualStart);
		const ends_at = fromLocalInput(manualEnd);
		if (!starts_at || !ends_at || ends_at <= starts_at) {
			toast.error('Give a start and an end, with the end after the start.');
			return;
		}
		try {
			await addDemandWindow(token, caseStudyId, { starts_at, ends_at, label: manualLabel || null });
			manualStart = manualEnd = manualLabel = '';
			await load();
			toast.success('Window added.');
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const remove = async (window) => {
		if (!confirm('Remove this window? Past popups that used it keep their record.')) return;
		try {
			await removeDemandWindow(token, caseStudyId, window.id);
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const downloadSample = () => {
		const blob = new Blob([SAMPLE], { type: 'text/csv' });
		const url = URL.createObjectURL(blob);
		const link = document.createElement('a');
		link.href = url;
		link.download = 'high-demand-windows.csv';
		link.click();
		URL.revokeObjectURL(url);
	};

	const STATE_TONE = {
		live: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
		upcoming: 'bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400',
		past: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-500'
	};
</script>

<div class="flex flex-col gap-4">
	<!-- Upload -->
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
		<div class="text-sm font-medium">Load high-demand windows from CSV</div>
		<div class="text-xs text-gray-400 mt-0.5 mb-3">
			Columns <code class="text-[11px]">start</code>, <code class="text-[11px]">end</code> and an
			optional <code class="text-[11px]">label</code>. Times are read in
			<strong>{timezone || 'the case study timezone'}</strong> unless a row carries its own offset.
		</div>

		<div class="flex flex-wrap items-center gap-2">
			<input
				bind:this={fileInput}
				type="file"
				accept=".csv,text/csv"
				on:change={onFile}
				class="text-sm file:mr-3 file:text-sm file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-gray-50 dark:file:bg-gray-850 file:text-inherit"
			/>
			<button class="text-xs text-blue-500 hover:underline" on:click={downloadSample}>
				Download a sample file
			</button>
		</div>

		{#if preview}
			<div class="mt-4 rounded-lg bg-gray-50 dark:bg-gray-850 p-3">
				<div class="text-sm font-medium mb-2">
					{preview.windows.length} window{preview.windows.length === 1 ? '' : 's'} ready to import
					{#if preview.skipped}
						<span class="text-amber-600 dark:text-amber-400">
							· {preview.skipped} row{preview.skipped === 1 ? '' : 's'} skipped
						</span>
					{/if}
				</div>

				<div class="max-h-48 overflow-y-auto text-xs">
					<table class="w-full">
						<tbody>
							{#each preview.windows as w}
								<tr class="border-b border-gray-100 dark:border-gray-800/50">
									<td class="py-1 pr-3 text-gray-400">row {w.row}</td>
									<td class="py-1 pr-3">{w.local_start.replace('T', ' ').slice(0, 16)}</td>
									<td class="py-1 pr-3">→ {w.local_end.replace('T', ' ').slice(0, 16)}</td>
									<td class="py-1 pr-3 text-gray-500">{w.duration_minutes} min</td>
									<td class="py-1 text-gray-500 truncate">{w.label ?? ''}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				{#if preview.warnings?.length}
					<div class="mt-2 text-xs text-amber-600 dark:text-amber-400 flex flex-col gap-0.5">
						{#each preview.warnings as warning}
							<div>{warning}</div>
						{/each}
					</div>
				{/if}

				<div class="flex flex-wrap items-center gap-3 mt-3">
					<label class="flex items-center gap-2 text-xs">
						<input type="checkbox" bind:checked={replaceExisting} />
						Replace the windows already loaded
					</label>
					<button
						class="text-sm px-3 py-1.5 rounded-lg bg-black dark:bg-white text-white dark:text-black font-medium disabled:opacity-50"
						disabled={importing || preview.windows.length === 0}
						on:click={confirmImport}
					>
						{importing ? 'Importing…' : 'Import'}
					</button>
					<button
						class="text-sm px-3 py-1.5 rounded-lg bg-white dark:bg-gray-800"
						on:click={() => {
							preview = null;
							pendingFile = null;
							if (fileInput) fileInput.value = '';
						}}
					>
						Cancel
					</button>
				</div>
			</div>
		{/if}
	</div>

	<!-- Manual add -->
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
		<div class="text-sm font-medium mb-3">Or add one by hand</div>
		<div class="flex flex-wrap items-end gap-2">
			<div>
				<label class="text-xs text-gray-500" for="dw-start">Start</label>
				<input
					id="dw-start"
					type="datetime-local"
					bind:value={manualStart}
					class="block mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
				/>
			</div>
			<div>
				<label class="text-xs text-gray-500" for="dw-end">End</label>
				<input
					id="dw-end"
					type="datetime-local"
					bind:value={manualEnd}
					class="block mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
				/>
			</div>
			<div class="flex-1 min-w-[160px]">
				<label class="text-xs text-gray-500" for="dw-label">Label</label>
				<input
					id="dw-label"
					bind:value={manualLabel}
					placeholder="Optional"
					class="block w-full mt-1 text-sm rounded-lg px-3 py-2 bg-gray-50 dark:bg-gray-850 outline-none"
				/>
			</div>
			<button
				class="text-sm px-3 py-2 rounded-lg bg-gray-50 dark:bg-gray-850"
				on:click={addManual}
			>
				Add
			</button>
		</div>
	</div>

	<!-- Current windows -->
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
		<div
			class="px-4 py-3 border-b border-gray-100 dark:border-gray-850 flex items-center justify-between"
		>
			<div class="text-sm font-medium">
				Loaded windows
				<span class="text-gray-400 font-normal">({windows.length})</span>
			</div>
			<button class="text-xs text-gray-400 hover:underline" on:click={load}>Refresh</button>
		</div>

		{#if loading}
			<div class="py-12 text-center text-sm text-gray-400">Loading…</div>
		{:else}
			<div class="max-h-96 overflow-y-auto">
				<table class="w-full text-sm">
					<tbody>
						{#each windows as w}
							<tr class="border-b border-gray-50 dark:border-gray-850/50">
								<td class="px-4 py-2 w-20">
									<span
										class="text-[10px] px-1.5 py-0.5 rounded-full uppercase tracking-wide {STATE_TONE[
											w.state
										]}"
									>
										{w.state}
									</span>
								</td>
								<td class="px-2 py-2">{formatStamp(w.starts_at)}</td>
								<td class="px-2 py-2 text-gray-500">→ {formatStamp(w.ends_at)}</td>
								<td class="px-2 py-2 text-gray-500 tabular-nums">{w.duration_minutes} min</td>
								<td class="px-2 py-2 truncate max-w-[220px]">{w.label ?? ''}</td>
								<td class="px-2 py-2 text-xs text-gray-400">{w.source}</td>
								<td class="px-4 py-2 text-right">
									<button
										class="text-xs text-gray-400 hover:text-red-500"
										on:click={() => remove(w)}
									>
										Remove
									</button>
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="7" class="px-4 py-12 text-center text-gray-400">
									No windows loaded. Upload a CSV to tell the study when demand is high.
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	{#if imports.length}
		<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
			<div class="text-sm font-medium mb-2">Import history</div>
			<div class="flex flex-col gap-1.5 text-xs">
				{#each imports as record}
					<div class="flex flex-wrap items-center gap-2 text-gray-500">
						<span class="text-gray-400">{formatStamp(record.imported_at)}</span>
						<span class="truncate">{record.filename ?? 'upload'}</span>
						<span>· {record.row_count} imported</span>
						{#if record.skipped_count}
							<span class="text-amber-600 dark:text-amber-400">· {record.skipped_count} skipped</span>
						{/if}
						{#if record.replaced}
							<span>· replaced previous</span>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
