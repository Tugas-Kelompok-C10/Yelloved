(() => {
    const root = document.querySelector('.explore-page');
    if (!root) return;
    const states = new Map();
    const pending = new Set();
    const feedback = document.createElement('p');
    feedback.className = 'explore-sr-only';
    feedback.setAttribute('role', 'status');
    feedback.setAttribute('aria-live', 'polite');
    root.append(feedback);

    function paint(id, saved, animate = false) {
        root.querySelectorAll('[data-item-favorite]').forEach(button => {
            if (button.dataset.itemFavorite !== String(id)) return;
            button.classList.toggle('is-favorited', saved);
            button.setAttribute('aria-pressed', String(saved));
            const label = saved ? 'Remove from favorites' : 'Save to favorites';
            button.setAttribute('aria-label', label);
            button.title = label;
            button.disabled = pending.has(String(id));
            if (animate) {
                button.classList.remove('favorite-pop');
                void button.offsetWidth;
                button.classList.add('favorite-pop');
            }
        });
    }

    root.addEventListener('click', async event => {
        const button = event.target.closest('[data-item-favorite]');
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();
        if (button.dataset.authenticated !== 'true') {
            window.location.assign(button.dataset.loginUrl);
            return;
        }
        const id = button.dataset.itemFavorite;
        if (pending.has(id)) return;
        pending.add(id);
        button.disabled = true;
        feedback.textContent = '';
        try {
            const response = await fetch(button.dataset.url, {
                method: 'POST', credentials: 'same-origin',
                headers: {'X-CSRFToken': button.dataset.csrf, 'Accept': 'application/json'}
            });
            if (response.redirected) {
                window.location.assign(button.dataset.loginUrl);
                return;
            }
            if (!response.ok) throw new Error('Favorite failed');
            const data = await response.json();
            if (data.item_id !== Number(id) || typeof data.is_favorited !== 'boolean') throw new Error('Invalid response');
            states.set(id, data.is_favorited);
            pending.delete(id);
            paint(id, data.is_favorited, true);
            feedback.className = 'explore-sr-only';
            feedback.textContent = data.is_favorited ? 'Item saved to favorites.' : 'Item removed from favorites.';
            // Keep an already-open Catalogue/detail tab in sync too.
            try { localStorage.setItem('items-favorite-change', JSON.stringify({...data, changed: Date.now()})); } catch (_) { /* Storage may be unavailable. */ }
        } catch (_) {
            feedback.className = 'explore-feedback';
            feedback.textContent = 'Unable to update favorites. Please try again.';
        } finally {
            pending.delete(id);
            button.disabled = false;
        }
    });
    root.addEventListener('animationend', event => {
        if (event.target.matches('[data-item-favorite]')) event.target.classList.remove('favorite-pop');
    });
    const results = document.getElementById('explore-results');
    if (results) new MutationObserver(() => {
        states.forEach((saved, id) => paint(id, saved));
    }).observe(results, {childList: true});
    window.addEventListener('storage', event => {
        if (event.key !== 'items-favorite-change' || !event.newValue) return;
        try {
            const data = JSON.parse(event.newValue);
            if (!Number.isInteger(data.item_id) || typeof data.is_favorited !== 'boolean') return;
            states.set(String(data.item_id), data.is_favorited);
            paint(data.item_id, data.is_favorited);
        } catch (_) { /* Ignore unrelated/invalid storage data. */ }
    });
    window.addEventListener('pageshow', event => {
        if (event.persisted) window.location.reload();
    });
})();
