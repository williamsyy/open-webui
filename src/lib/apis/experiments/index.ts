import { WEBUI_API_BASE_URL } from '$lib/constants';

// ---- Experiments CRUD ----

export const getExperiments = async (token: string = '') => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res?.experiments ?? [];
};

export const createExperiment = async (token: string, data: object) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getExperiment = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${id}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateExperiment = async (token: string, id: string, data: object) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${id}`, {
		method: 'PUT',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteExperiment = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${id}`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// ---- Groups ----

export const getExperimentGroups = async (token: string, experimentId: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${experimentId}/groups`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res ?? [];
};

export const createExperimentGroup = async (
	token: string,
	experimentId: string,
	data: { name: string; type: string }
) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${experimentId}/groups`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteExperimentGroup = async (
	token: string,
	experimentId: string,
	groupId: string
) => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/experiments/${experimentId}/groups/${groupId}`,
		{
			method: 'DELETE',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// ---- Assignments ----

export const getExperimentAssignments = async (token: string, experimentId: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${experimentId}/assignments`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res?.assignments ?? [];
};

export const assignUsers = async (
	token: string,
	experimentId: string,
	data: { group_id: string; user_ids: string[] }
) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${experimentId}/assignments`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const removeAssignment = async (
	token: string,
	experimentId: string,
	userId: string
) => {
	let error = null;

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/experiments/${experimentId}/assignments/${userId}`,
		{
			method: 'DELETE',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const randomizeUsers = async (
	token: string,
	experimentId: string,
	data: { user_ids: string[]; treatment_ratio: number }
) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${experimentId}/randomize`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// ---- Intervention (user-facing) ----

export const checkIntervention = async (
	token: string,
	messageCount: number = 0,
	tokenUsage: number = 0
) => {
	let error = null;

	const params = new URLSearchParams({
		message_count: messageCount.toString(),
		token_usage: tokenUsage.toString()
	});

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/check?${params}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const recordExperimentEvent = async (
	token: string,
	data: {
		experiment_id: string;
		event_type: string;
		chat_id?: string;
		event_data?: object;
	}
) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/events`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(data)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

// ---- Analytics (admin) ----

export const getExperimentAnalytics = async (
	token: string,
	experimentId: string,
	params: { start_date?: number; end_date?: number } = {}
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (params.start_date) searchParams.set('start_date', params.start_date.toString());
	if (params.end_date) searchParams.set('end_date', params.end_date.toString());

	const url = `${WEBUI_API_BASE_URL}/experiments/${experimentId}/analytics?${searchParams}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getExperimentDailyTrends = async (
	token: string,
	experimentId: string,
	params: { group_id?: string; start_date?: number; end_date?: number } = {}
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (params.group_id) searchParams.set('group_id', params.group_id);
	if (params.start_date) searchParams.set('start_date', params.start_date.toString());
	if (params.end_date) searchParams.set('end_date', params.end_date.toString());

	const url = `${WEBUI_API_BASE_URL}/experiments/${experimentId}/analytics/daily?${searchParams}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getPerUserAnalytics = async (
	token: string,
	experimentId: string,
	params: { start_date?: number; end_date?: number } = {}
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (params.start_date) searchParams.set('start_date', params.start_date.toString());
	if (params.end_date) searchParams.set('end_date', params.end_date.toString());

	const url = `${WEBUI_API_BASE_URL}/experiments/${experimentId}/analytics/users?${searchParams}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUserHourlyActivity = async (
	token: string,
	experimentId: string,
	userId: string,
	params: { start_date?: number; end_date?: number } = {}
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (params.start_date) searchParams.set('start_date', params.start_date.toString());
	if (params.end_date) searchParams.set('end_date', params.end_date.toString());

	const url = `${WEBUI_API_BASE_URL}/experiments/${experimentId}/analytics/users/${userId}?${searchParams}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getExperimentEvents = async (
	token: string,
	experimentId: string,
	params: {
		event_type?: string;
		user_id?: string;
		start_date?: number;
		end_date?: number;
		skip?: number;
		limit?: number;
	} = {}
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (params.event_type) searchParams.set('event_type', params.event_type);
	if (params.user_id) searchParams.set('user_id', params.user_id);
	if (params.start_date) searchParams.set('start_date', params.start_date.toString());
	if (params.end_date) searchParams.set('end_date', params.end_date.toString());
	if (params.skip !== undefined) searchParams.set('skip', params.skip.toString());
	if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());

	const url = `${WEBUI_API_BASE_URL}/experiments/${experimentId}/events?${searchParams}`;

	const res = await fetch(url, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const exportExperimentData = async (token: string, experimentId: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/experiments/${experimentId}/export`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getPostponements = async (
	token: string,
	experimentId: string,
	params: {
		user_id?: string;
		status?: string;
		skip?: number;
		limit?: number;
	} = {}
) => {
	let error = null;

	const queryParams = new URLSearchParams();
	if (params.user_id) queryParams.set('user_id', params.user_id);
	if (params.status) queryParams.set('status', params.status);
	if (params.skip !== undefined) queryParams.set('skip', params.skip.toString());
	if (params.limit !== undefined) queryParams.set('limit', params.limit.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/experiments/${experimentId}/postponements?${queryParams}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
