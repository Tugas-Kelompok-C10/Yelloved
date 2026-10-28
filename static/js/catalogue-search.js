/* Shared navbar search: debounce requests and discard outdated responses. */
(() => {
    const form = document.querySelector('[data-catalogue-search]');
    if (!form) return;
    const input = form.querySelector('input');
    const results = form.querySelector('.nav-search-results');
    // Keep confirmed search terms in this browser, never result HTML.
    const historyKey = 'yelloved.recent-searches';
    let history = [];
    try {
        const saved = JSON.parse(localStorage.getItem(historyKey) || '[]');
        if (Array.isArray(saved)) history = saved.filter(value => typeof value === 'string' && value.trim()).slice(0, 6);
    } catch (_) { /* Search still works when browser storage is unavailable. */ }
    const persistHistory = () => {
        try { localStorage.setItem(historyKey, JSON.stringify(history)); } catch (_) { /* In-memory fallback. */ }
    };
    const remember = (value) => {
        const query = value.trim().slice(0, 200);
        if (!query) return;
        history = [query, ...history.filter(item => item.toLowerCase() !== query.toLowerCase())].slice(0, 6);
        persistHistory();
    };
    const renderHistory = () => {
        results.replaceChildren();
        const header = document.createElement('div');
        header.className = 'nav-search-history-header';
        const title = document.createElement('h3');
        title.textContent = 'Recent searches';
        header.append(title);
        if (history.length) {
            const clear = document.createElement('button');
            clear.type = 'button';
            clear.className = 'nav-search-history-clear';
            clear.textContent = 'Clear all';
            clear.addEventListener('click', () => {
                history = [];
                persistHistory();
                input.focus();
                renderHistory();
            });
            header.append(clear);
        }
        results.append(header);
        if (!history.length) {
            const empty = document.createElement('p');
            empty.textContent = 'No recent searches yet.';
            results.append(empty);
        }
        history.forEach(query => {
            const row = document.createElement('div');
            row.className = 'nav-search-history-row';
            const repeat = document.createElement('button');
            repeat.type = 'button';
            repeat.className = 'nav-search-history-query';
            repeat.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
            const label = document.createElement('span');
            label.textContent = query;
            repeat.append(label);
            repeat.addEventListener('click', () => {
                input.value = query;
                syncClearButton();
                remember(query);
                input.focus();
                openPreview();
            });
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.className = 'nav-search-history-remove';
            remove.setAttribute('aria-label', `Remove ${query} from recent searches`);
            remove.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
            remove.addEventListener('click', () => {
                history = history.filter(item => item !== query);
                persistHistory();
                input.focus();
                renderHistory();
            });
            row.append(repeat, remove);
            results.append(row);
        });
    };
    const clearButton = form.querySelector('.nav-search-clear');
    const syncClearButton = () => { clearButton.hidden = !input.value; };
    syncClearButton();
    let timer, controller, version = 0, completedQuery = '';
    const close = () => { results.hidden = true; input.setAttribute('aria-expanded', 'false'); };
    const open = () => { results.hidden = false; input.setAttribute('aria-expanded', 'true'); };
    const showPreview = () => {
        if (input.value.trim()) {
            const message = document.createElement('p');
            message.textContent = 'Finding items and wanted posts…';
            results.replaceChildren(message);
        } else renderHistory();
        open();
    };
    const search = async () => {
        const query = input.value.trim();
        const current = ++version;
        controller?.abort();
        if (!query) { renderHistory(); open(); return; }
        controller = new AbortController();
        const url = new URL(form.action);
        url.searchParams.set('q', query);
        try {
            const response = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, signal: controller.signal });
            if (!response.ok) throw new Error('Search unavailable');
            const data = await response.json();
            if (current !== version || input.value.trim() !== query) return;
            completedQuery = query;
            results.innerHTML = data.html;
            if (!form.contains(document.activeElement)) return;
            results.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        } catch (error) {
            if (error.name !== 'AbortError' && current === version && form.contains(document.activeElement)) {
                results.replaceChildren();
                const link = document.createElement('a');
                link.href = url;
                link.className = 'nav-search-all';
                link.append(form.querySelector('svg').cloneNode(true));
                const label = document.createElement('span');
                label.textContent = 'Search is taking a moment. View all results';
                link.append(label);
                results.append(link);
                results.hidden = false;
                input.setAttribute('aria-expanded', 'true');
            }
        }
    };
    input.addEventListener('input', () => {
        syncClearButton();
        clearTimeout(timer);
        ++version;
        controller?.abort();
        showPreview();
        if (input.value.trim()) timer = setTimeout(search, 300);
    });
    clearButton.addEventListener('click', () => {
        if (input.value.trim() === completedQuery) remember(completedQuery);
        clearTimeout(timer);
        ++version;
        controller?.abort();
        input.value = '';
        syncClearButton();
        input.focus();
        showPreview();
        search();
    });
    const openPreview = () => {
        clearTimeout(timer);
        showPreview();
        search();
    };
    input.addEventListener('focus', openPreview);
    input.addEventListener('click', () => { if (results.hidden) openPreview(); });
    form.addEventListener('click', event => {
        if (event.target === form || event.target === form.querySelector('svg')) input.focus();
    });
    form.addEventListener('submit', () => remember(input.value));
    results.addEventListener('click', event => {
        if (event.target.closest('a')) remember(input.value);
    });
    // A query on the results page also counts when reached from another link.
    if (input.value.trim()) remember(input.value);
    form.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            input.focus();
            clearTimeout(timer);
            ++version;
            controller?.abort();
            close();
        }
        if (event.key === 'ArrowDown' && !results.hidden) {
            const links = [...results.querySelectorAll('a, button')];
            const next = links[links.indexOf(document.activeElement) + 1];
            if (next) { event.preventDefault(); next.focus(); }
        }
        if (event.key === 'ArrowUp' && !results.hidden) {
            event.preventDefault();
            const links = [...results.querySelectorAll('a, button')];
            (links[links.indexOf(document.activeElement) - 1] || input).focus();
        }
    });
    document.addEventListener('click', event => {
        // History buttons can be removed while their click is still bubbling.
        if (!event.composedPath().includes(form)) {
            if (input.value.trim() === completedQuery) remember(completedQuery);
            close();
        }
    });
    form.addEventListener('focusout', () => setTimeout(() => { if (!form.contains(document.activeElement)) close(); }, 0));
})();
