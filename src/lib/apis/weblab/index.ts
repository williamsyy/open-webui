import { WEBUI_API_BASE_URL } from '$lib/constants';

const BASE = `${WEBUI_API_BASE_URL}/weblab`;

const request = async (
	token: string,
	path: string,
	{ method = 'GET', body = null, raw = false }: { method?: string; body?: any; raw?: boolean } = {}
) => {
	let error = null;

	const headers: Record<string, string> = {
		Accept: 'application/json',
		authorization: `Bearer ${token}`
	};

	let payload: any = undefined;
	if (body instanceof FormData) {
		payload = body;
	} else if (body !== null) {
		headers['Content-Type'] = 'application/json';
		payload = JSON.stringify(body);
	}

	const res = await fetch(`${BASE}${path}`, { method, headers, body: payload })
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return raw ? res : res.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/* ── Case studies ─────────────────────────────────────────────── */

export const getCaseStudies = (token: string) => request(token, '/case-studies');

export const getCaseStudy = (token: string, id: string) => request(token, `/case-studies/${id}`);

export const createCaseStudy = (token: string, payload: object) =>
	request(token, '/case-studies', { method: 'POST', body: payload });

export const updateCaseStudy = (token: string, id: string, payload: object) =>
	request(token, `/case-studies/${id}`, { method: 'PUT', body: payload });

export const archiveCaseStudy = (token: string, id: string) =>
	request(token, `/case-studies/${id}`, { method: 'DELETE' });

/* ── Participants & arms ──────────────────────────────────────── */

export const getParticipants = (token: string, id: string) =>
	request(token, `/case-studies/${id}/participants`);

export const enrollParticipants = (token: string, id: string, payload: object) =>
	request(token, `/case-studies/${id}/participants`, { method: 'POST', body: payload });

export const endParticipation = (token: string, id: string, userId: string) =>
	request(token, `/case-studies/${id}/participants/${userId}`, { method: 'DELETE' });

export const setMembership = (token: string, id: string, payload: object) =>
	request(token, `/case-studies/${id}/membership`, { method: 'POST', body: payload });

export const randomizeParticipants = (token: string, id: string, payload: object) =>
	request(token, `/case-studies/${id}/randomize`, { method: 'POST', body: payload });

export const getParticipantHistory = (token: string, id: string, userId: string) =>
	request(token, `/case-studies/${id}/participants/${userId}/history`);

export const getCandidateUsers = (token: string, caseStudyId?: string, query?: string) => {
	const params = new URLSearchParams();
	if (caseStudyId) params.set('case_study_id', caseStudyId);
	if (query) params.set('query', query);
	return request(token, `/candidates?${params.toString()}`);
};

/* ── Demand windows ───────────────────────────────────────────── */

export const getDemandWindows = (token: string, id: string, includeInactive = false) =>
	request(token, `/case-studies/${id}/demand-windows?include_inactive=${includeInactive}`);

export const previewDemandCsv = (token: string, id: string, file: File, timezone?: string) => {
	const form = new FormData();
	form.append('file', file);
	const params = timezone ? `?timezone=${encodeURIComponent(timezone)}` : '';
	return request(token, `/case-studies/${id}/demand-windows/preview${params}`, {
		method: 'POST',
		body: form
	});
};

export const importDemandCsv = (
	token: string,
	id: string,
	file: File,
	{ timezone, replace = false }: { timezone?: string; replace?: boolean } = {}
) => {
	const form = new FormData();
	form.append('file', file);
	const params = new URLSearchParams();
	if (timezone) params.set('timezone', timezone);
	params.set('replace', String(replace));
	return request(token, `/case-studies/${id}/demand-windows/import?${params.toString()}`, {
		method: 'POST',
		body: form
	});
};

export const addDemandWindow = (token: string, id: string, payload: object) =>
	request(token, `/case-studies/${id}/demand-windows`, { method: 'POST', body: payload });

export const removeDemandWindow = (token: string, id: string, windowId: string) =>
	request(token, `/case-studies/${id}/demand-windows/${windowId}`, { method: 'DELETE' });

export const getDemandImports = (token: string, id: string) =>
	request(token, `/case-studies/${id}/demand-windows/imports`);

/* ── Analytics ────────────────────────────────────────────────── */

export const getUsageOverview = (
	token: string,
	{
		start,
		end,
		caseStudyId,
		groupKind,
		timezone
	}: {
		start?: number;
		end?: number;
		caseStudyId?: string;
		groupKind?: string;
		timezone?: string;
	} = {}
) => {
	const params = new URLSearchParams();
	if (start) params.set('start', String(start));
	if (end) params.set('end', String(end));
	if (caseStudyId) params.set('case_study_id', caseStudyId);
	if (groupKind) params.set('group_kind', groupKind);
	if (timezone) params.set('timezone', timezone);
	return request(token, `/usage/overview?${params.toString()}`);
};

export const getCaseStudyReport = (token: string, id: string) =>
	request(token, `/case-studies/${id}/report`);

export const getInterventions = (token: string, id: string, limit = 200) =>
	request(token, `/case-studies/${id}/interventions?limit=${limit}`);

export const getStudyEvents = (token: string, id: string, limit = 300) =>
	request(token, `/case-studies/${id}/events?limit=${limit}`);

/* ── Database & backups ───────────────────────────────────────── */

export const getDbInfo = (token: string) => request(token, '/db/info');
export const getBackups = (token: string) => request(token, '/db/backups');
export const createBackup = (token: string) => request(token, '/db/backups', { method: 'POST' });
export const verifyBackup = (token: string, filename: string) =>
	request(token, `/db/backups/${filename}/verify`);
export const restoreBackup = (token: string, filename: string) =>
	request(token, `/db/backups/${filename}/restore`, { method: 'POST' });

export const exportUrl = (id: string, format = 'json') =>
	`${BASE}/case-studies/${id}/export?format=${format}`;
export const downloadDbUrl = () => `${BASE}/db/download`;

/* ── Chat-side ────────────────────────────────────────────────── */

export const checkIntervention = (token: string, chatId?: string) =>
	request(token, `/check${chatId ? `?chat_id=${encodeURIComponent(chatId)}` : ''}`);

export const recordDecision = (
	token: string,
	interventionId: string,
	decision: 'accepted' | 'declined' | 'dismissed',
	clientMeta?: object
) =>
	request(token, '/decision', {
		method: 'POST',
		body: { intervention_id: interventionId, decision, client_meta: clientMeta ?? null }
	});

export const releasePostponement = (token: string, reason = 'elapsed', caseStudyId?: string) =>
	request(token, '/release', {
		method: 'POST',
		body: { reason, case_study_id: caseStudyId ?? null }
	});
