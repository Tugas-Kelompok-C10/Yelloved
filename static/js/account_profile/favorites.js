(() => {
    const root = document.querySelector('.public-profile-favorites');
    if (!root) return;
    const content = root.querySelector('#profile-favorites-content');
    const feedback = root.querySelector('.profile-favorites-feedback');
    let controller;
    let busy = false;
    function announce(text, error = false) {
        feedback.textContent = text;
        feedback.hidden = !text;
        feedback.classList.toggle('is-error', error);
    }
    async function load(url, updateHistory = false) {
        if (controller) controller.abort();
        const active = controller = new AbortController();
        const endpoint = new URL(url, window.location.href);
        endpoint.searchParams.set('fragment', 'favorites');
        content.setAttribute('aria-busy', 'true');
        try {
            const response = await fetch(endpoint, {credentials: 'same-origin', signal: active.signal});
            if (response.redirected) { window.location.assign(response.url); return; }
            if (!response.ok) throw new Error('Unable to load favorites');
            const html = await response.text();
            if (active !== controller) return;
            // This is our authenticated, escaped Django partial, never external HTML.
            content.innerHTML = html;
            if (updateHistory) {
                endpoint.searchParams.delete('fragment');
                history.pushState(null, '', endpoint);
            }
        } finally {
            if (active === controller) content.setAttribute('aria-busy', 'false');
        }
    }
    root.addEventListener('click', async event => {
        const filter = event.target.closest('.profile-favorites-filters a, .profile-favorites-show-all');
        if (filter && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {
            event.preventDefault();
            if (busy) return;
            announce('Loading favorites…');
            try { await load(filter.href, true); announce(''); }
            catch (error) { if (error.name !== 'AbortError') announce('Unable to load favorites. Please try again.', true); }
            return;
        }
        const button = event.target.closest('[data-item-favorite]');
        if (!button) return;
        event.preventDefault(); event.stopPropagation();
        if (busy) return;
        busy = true;
        button.disabled = true;
        let removed = false;
        const card = button.closest('[data-favorite-card]');
        const nextFocusId = card.nextElementSibling?.dataset.favoriteCard || card.previousElementSibling?.dataset.favoriteCard;
        try {
            if (controller) controller.abort();
            const response = await fetch(button.dataset.url, {
                method: 'POST', credentials: 'same-origin',
                headers: {'X-CSRFToken': button.dataset.csrf, 'Accept': 'application/json'}
            });
            if (response.redirected) { window.location.assign(button.dataset.loginUrl); return; }
            if (!response.ok) throw new Error('Unable to update favorite');
            const data = await response.json();
            if (data.item_id !== Number(button.dataset.itemFavorite) || typeof data.is_favorited !== 'boolean') throw new Error('Invalid favorite response');
            // The existing endpoint toggles. Remove only after it confirms unsaved state.
            if (!data.is_favorited) {
                removed = true;
                card.remove();
                const count = content.querySelector('[data-favorites-count]');
                count.textContent = Math.max(0, Number(count.textContent) - 1);
            }
            try { localStorage.setItem('items-favorite-change', JSON.stringify({...data, changed: Date.now()})); } catch (_) { /* Storage is optional. */ }
            await load(window.location.href);
            announce(removed ? 'Item removed from favorites.' : 'Item saved to favorites.');
            const next = nextFocusId && content.querySelector(`[data-favorite-card="${nextFocusId}"] [data-item-favorite]`);
            (next || content.querySelector('.profile-favorites-filters a.is-active'))?.focus();
        } catch (_) {
            announce(removed ? 'Favorite removed. Reload this page to refresh the list.' : 'Unable to update favorites. Please try again.', true);
        } finally { busy = false; button.disabled = false; }
    });
    root.addEventListener('error', event => {
        const image = event.target;
        if (!image.matches?.('[data-profile-image]')) return;
        if (image.dataset.fallback && !image.dataset.triedFallback) {
            image.dataset.triedFallback = 'true'; image.src = image.dataset.fallback;
        } else { image.hidden = true; }
    }, true);
    window.addEventListener('popstate', () => {
        if (new URLSearchParams(location.search).get('tab') !== 'favorites') { location.reload(); return; }
        load(location.href).catch(() => announce('Unable to load favorites. Please refresh the page.', true));
    });
    window.addEventListener('storage', event => {
        if (event.key === 'items-favorite-change' && !busy) load(location.href).catch(() => announce('Refresh this page to see the latest favorites.', true));
    });
    window.addEventListener('pageshow', event => {
        if (event.persisted) location.reload();
    });
})();
