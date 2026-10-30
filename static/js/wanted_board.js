/* HTMX fetches/swaps Wanted results. JS only coordinates controls and feedback. */
(() => {
    let destroy = () => {};
    const init = () => {
        const form = document.querySelector('[data-ajax-search]');
        if (!form || form.dataset.searchBound) return;
        destroy();
        form.dataset.searchBound = 'true';
        const input = form.querySelector('[name=q]');
        const category = form.querySelector('[name=category]');
        const sort = form.querySelector('[name=sort]');
        const page = form.querySelector('[name=page]');
        const results = document.getElementById('wanted-results');
        const chips = [...form.querySelectorAll('[data-category-chip]')];
        const sortButton = form.querySelector('[data-wanted-sort]');
        const listeners = new AbortController();
        let active, disposed = false, paginationRequested = false;
        let confirmed = {category: category.value, sort: sort.value, page: page.value};
        const on = (element, name, handler) => element.addEventListener(name, handler, {signal: listeners.signal});
        const busy = value => {
            const grid = results.querySelector('.wanted-grid');
            grid?.classList.toggle('is-loading', value);
            grid?.setAttribute('aria-busy', String(value));
        };
        const controls = state => {
            category.value = state.category;
            sort.value = state.sort;
            if (state.page !== undefined) page.value = state.page;
            chips.forEach(chip => {
                const selected = chip.dataset.categoryChip === category.value;
                chip.classList.toggle('is-active', selected);
                chip.setAttribute('aria-pressed', String(selected));
            });
            sortButton.dataset.sort = sort.value;
            sortButton.setAttribute('aria-pressed', String(Boolean(sort.value)));
            const label = sort.value === 'budget_asc' ? 'Lowest budget first' : sort.value === 'budget_desc' ? 'Highest budget first' : 'Newest posts first';
            sortButton.title = label;
            sortButton.setAttribute('aria-label', `${label}. Click for ${sort.value === 'budget_asc' ? 'highest' : 'lowest'} first.`);
            form.querySelector('[data-wanted-sort-status]').textContent = label;
        };
        const cancel = () => {
            const previous = active;
            active = null;
            previous?.xhr.abort();
            busy(false);
        };
        destroy = () => {disposed = true; cancel(); listeners.abort();};

        on(input, 'input', () => {cancel(); page.value = '1'; paginationRequested = false;});
        chips.forEach(chip => on(chip, 'click', () => {
            controls({category: chip.dataset.categoryChip, sort: sort.value});
            page.value = '1'; paginationRequested = false;
            form.requestSubmit();
        }));
        on(sortButton, 'click', () => {
            controls({category: category.value, sort: sort.value === 'budget_asc' ? 'budget_desc' : 'budget_asc'});
            page.value = '1'; paginationRequested = false;
            form.requestSubmit();
        });
        on(results, 'click', event => {
            const link = event.target.closest('[data-wanted-page]');
            if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
            event.preventDefault();
            page.value = link.dataset.wantedPage;
            paginationRequested = true;
            // One HTMX form handles every request, also cancelling a pending search debounce.
            form.requestSubmit();
        });
        on(document, 'htmx:configRequest', event => {
            if (event.detail.target !== results) return;
            event.detail.parameters.q = input.value.trim().slice(0, 70);
        });
        on(document, 'htmx:beforeRequest', event => {
            if (event.detail.target !== results) return;
            active = {xhr: event.detail.xhr, scroll: paginationRequested};
            paginationRequested = false;
            busy(true);
        });
        on(document, 'htmx:beforeSwap', event => {
            if (event.detail.target !== results) return;
            // A cancelled request or removed board must never replace newer results.
            if (disposed || !form.isConnected || active?.xhr !== event.detail.xhr) event.preventDefault();
        });
        on(document, 'htmx:afterSwap', event => {
            if (event.detail.target !== results || active?.xhr !== event.detail.xhr) return;
            const state = results.querySelector('[data-wanted-state]').dataset;
            confirmed = {category: state.category, sort: state.sort, page: state.page};
            controls(confirmed);
            window.history.replaceState(window.history.state, '', state.url);
            if (active.scroll) window.scrollTo({top: 0, left: 0, behavior: 'instant'});
        });
        on(document, 'htmx:afterRequest', event => {
            if (active?.xhr !== event.detail.xhr) return;
            busy(false);
            active = null;
            if (event.detail.failed) {
                controls(confirmed);
                window.YellovedToast?.show({type: 'error', title: 'Unable to search',
                    message: 'Your previous results are still shown. Check your connection, then press Enter in the search field to try again.'});
            }
        });
        // Create/Delete can mount a fresh board without loading another document.
        window.htmx?.process(form);
        window.htmx?.process(results);
    };
    window.YellovedWantedBoard = {init, destroy: () => destroy()};
    init();
})();
