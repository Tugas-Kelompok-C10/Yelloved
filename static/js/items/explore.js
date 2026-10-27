(() => {
    const form = document.getElementById('explore-filters');
    if (!form) return;
    const results = document.getElementById('explore-results');
    const loading = document.getElementById('explore-loading');
    const error = document.getElementById('explore-error');
    let controller;
    let timer;
    let requestedPage = 1;
    async function load(page = 1) {
        requestedPage = page;
        clearTimeout(timer);
        if (controller) controller.abort();
        controller = new AbortController();
        const active = controller;
        const params = new URLSearchParams(new FormData(form));
        params.set('page', page);
        loading.hidden = false;
        error.hidden = true;
        results.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(`${form.dataset.endpoint}?${params}`, {signal: active.signal, headers: {'Accept': 'application/json'}});
            if (!response.ok) throw new Error('Load failed');
            const data = await response.json();
            if (active !== controller) return;
            // HTML comes only from our Django partial, which escapes all item content.
            results.innerHTML = data.html;
            const url = new URL(form.action);
            url.search = params.toString();
            history.replaceState(null, '', url);
        } catch (failure) {
            if (failure.name !== 'AbortError' && active === controller) error.hidden = false;
        } finally {
            if (active === controller) {
                loading.hidden = true;
                results.setAttribute('aria-busy', 'false');
            }
        }
    }
    document.getElementById('explore-reset-filters').addEventListener('click', () => {
        // form.reset() would restore initial URL filters rather than the All choices.
        form.querySelectorAll('input[type="search"], select').forEach(field => { field.value = ''; });
        const advanced = form.querySelector('details');
        if (advanced) advanced.open = false;
        load(1);
    });
    form.addEventListener('submit', event => { event.preventDefault(); load(); });
    form.querySelector('input[name="q"]').addEventListener('input', () => {
        if (controller) controller.abort();
        clearTimeout(timer);
        timer = setTimeout(() => load(), 300);
    });
    form.querySelectorAll('select').forEach(select => select.addEventListener('change', () => load()));
    document.getElementById('explore-retry').addEventListener('click', () => load(requestedPage));
    results.addEventListener('click', event => {
        const link = event.target.closest('a[data-page]');
        if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
            event.preventDefault(); load(Number(link.dataset.page));
        }
    });
})();
