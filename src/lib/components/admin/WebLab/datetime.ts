// Helpers for moving between epoch seconds (what the study database stores)
// and the `datetime-local` input value the admin types into.

export const toLocalInput = (epochSeconds?: number | null): string => {
	if (!epochSeconds) return '';
	const d = new Date(epochSeconds * 1000);
	const pad = (n: number) => String(n).padStart(2, '0');
	return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

export const fromLocalInput = (value: string): number | null => {
	if (!value) return null;
	const ms = new Date(value).getTime();
	return Number.isNaN(ms) ? null : Math.floor(ms / 1000);
};

export const formatStamp = (epochSeconds?: number | null): string => {
	if (!epochSeconds) return '—';
	return new Date(epochSeconds * 1000).toLocaleString(undefined, {
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	});
};

export const formatDuration = (seconds?: number | null): string => {
	if (seconds === null || seconds === undefined) return '—';
	if (seconds < 60) return `${Math.round(seconds)}s`;
	const minutes = seconds / 60;
	if (minutes < 60) return `${minutes % 1 === 0 ? minutes : minutes.toFixed(1)} min`;
	const hours = minutes / 60;
	return `${hours % 1 === 0 ? hours : hours.toFixed(1)} h`;
};
