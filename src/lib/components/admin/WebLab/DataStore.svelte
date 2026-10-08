<script>
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	import {
		createBackup,
		downloadDbUrl,
		getBackups,
		getDbInfo,
		restoreBackup,
		verifyBackup
	} from '$lib/apis/weblab';
	import { formatStamp } from './datetime';

	export let token = '';

	let info = null;
	let backups = [];
	let busy = false;
	let verified = {};

	const load = async () => {
		try {
			[info, backups] = await Promise.all([getDbInfo(token), getBackups(token)]);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	onMount(load);

	const snapshot = async () => {
		busy = true;
		try {
			const result = await createBackup(token);
			toast.success(`Snapshot written: ${result.filename}`);
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
		busy = false;
	};

	const verify = async (filename) => {
		try {
			const result = await verifyBackup(token, filename);
			verified = { ...verified, [filename]: result };
			toast[result.ok ? 'success' : 'error'](
				result.ok ? 'Snapshot is intact.' : `Integrity check said: ${result.integrity}`
			);
		} catch (error) {
			toast.error(`${error}`);
		}
	};

	const restore = async (filename) => {
		if (
			!confirm(
				`Replace the live study database with ${filename}?\n\nThe current database is snapshotted first, and Open WebUI must be restarted afterwards.`
			)
		)
			return;
		busy = true;
		try {
			const result = await restoreBackup(token, filename);
			toast.success(
				`Restored from ${result.restored_from}. Restart Open WebUI to finish. Previous state saved as ${result.pre_restore_backup}.`
			);
			await load();
		} catch (error) {
			toast.error(`${error}`);
		}
		busy = false;
	};

	const bytes = (n) => {
		if (!n) return '—';
		const units = ['B', 'KB', 'MB', 'GB'];
		let value = n;
		let unit = 0;
		while (value >= 1024 && unit < units.length - 1) {
			value /= 1024;
			unit += 1;
		}
		return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
	};
</script>

<div class="flex flex-col gap-4 max-w-3xl">
	<div class="rounded-xl border border-gray-100 dark:border-gray-850 p-4">
		<div class="text-sm font-medium">The study database</div>
		<div class="text-xs text-gray-400 mt-0.5 mb-3">
			Separate from Open WebUI's own database. Everything the study needs lives here, so it
			survives an upgrade or a reset of the main app — copy this one file and you have the study.
		</div>

		{#if info}
			<div class="text-xs font-mono bg-gray-50 dark:bg-gray-850 rounded-lg px-3 py-2 break-all">
				{info.path}
			</div>

			<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-sm">
				<div>
					<div class="text-xs text-gray-400">Size</div>
					<div class="tabular-nums">{bytes(info.size)}</div>
				</div>
				<div>
					<div class="text-xs text-gray-400">Schema</div>
					<div class="tabular-nums">v{info.schema_version}</div>
				</div>
				<div>
					<div class="text-xs text-gray-400">Snapshots</div>
					<div class="tabular-nums">{info.backup_count}</div>
				</div>
				<div>
					<div class="text-xs text-gray-400">Kept</div>
					<div class="tabular-nums">last {info.retention}</div>
				</div>
			</div>

			<div class="grid grid-cols-3 sm:grid-cols-5 gap-2 mt-4">
				{#each Object.entries(info.row_counts) as [table, count]}
					<div class="rounded-lg bg-gray-50 dark:bg-gray-850 px-2.5 py-2">
						<div class="text-[10px] text-gray-400 truncate">{table.replace(/_/g, ' ')}</div>
						<div class="text-sm tabular-nums">{count.toLocaleString()}</div>
					</div>
				{/each}
			</div>

			<div class="flex flex-wrap gap-2 mt-4">
				<button
					class="text-sm px-3 py-1.5 rounded-lg bg-black dark:bg-white text-white dark:text-black font-medium disabled:opacity-50"
					disabled={busy}
					on:click={snapshot}
				>
					{busy ? 'Working…' : 'Take a snapshot now'}
				</button>
				<a
					href={downloadDbUrl()}
					class="text-sm px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-850"
				>
					Download the database
				</a>
			</div>
			<div class="text-[11px] text-gray-400 mt-2">
				A snapshot is taken automatically every {Math.round(info.interval_seconds / 3600)} hours
				and on startup.
			</div>
		{/if}
	</div>

	<div class="rounded-xl border border-gray-100 dark:border-gray-850 overflow-hidden">
		<div class="px-4 py-3 border-b border-gray-100 dark:border-gray-850 text-sm font-medium">
			Snapshots
		</div>
		<div class="max-h-96 overflow-y-auto">
			<table class="w-full text-sm">
				<tbody>
					{#each backups as file}
						<tr class="border-b border-gray-50 dark:border-gray-850/50">
							<td class="px-4 py-2 font-mono text-xs truncate max-w-[260px]">{file.filename}</td>
							<td class="px-2 py-2 text-gray-500 whitespace-nowrap">
								{formatStamp(file.created_at)}
							</td>
							<td class="px-2 py-2 text-gray-500 tabular-nums">{bytes(file.size)}</td>
							<td class="px-2 py-2 text-xs">
								{#if verified[file.filename]}
									<span
										class={verified[file.filename].ok
											? 'text-emerald-600 dark:text-emerald-400'
											: 'text-red-500'}
									>
										{verified[file.filename].integrity}
									</span>
								{/if}
							</td>
							<td class="px-4 py-2 text-right whitespace-nowrap">
								<button
									class="text-xs text-blue-500 hover:underline"
									on:click={() => verify(file.filename)}
								>
									Verify
								</button>
								<button
									class="text-xs text-gray-400 hover:text-amber-600 ml-2"
									disabled={busy}
									on:click={() => restore(file.filename)}
								>
									Restore
								</button>
							</td>
						</tr>
					{:else}
						<tr>
							<td colspan="5" class="px-4 py-12 text-center text-gray-400">
								No snapshots yet.
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
