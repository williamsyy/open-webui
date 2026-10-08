<script>
	import { user } from '$lib/stores';
	import WebLab from '$lib/components/admin/WebLab.svelte';
</script>

<WebLab token={localStorage.token} />
