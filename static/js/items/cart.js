(() => {
    const form = document.querySelector('.item-detail-page #item-add-to-cart-form');
    if (!form) return;
    const button = document.querySelector('.item-detail-page button[form="item-add-to-cart-form"]');
    let pending = false;
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (pending) return;
        pending = true;
        button.disabled = true;
        try {
            const response = await fetch(form.action, {
                method: 'POST', credentials: 'same-origin', body: new FormData(form),
                headers: {'Accept': 'application/json'}
            });
            if (response.redirected) {
                const login = new URL(form.dataset.loginUrl, location.href);
                if (new URL(response.url).pathname === login.pathname) {
                    location.assign(login); return;
                }
                throw new Error('Unable to add this item. Please try again.');
            }
            const json = response.headers.get('content-type')?.includes('application/json');
            const data = json ? await response.json() : {};
            if (!response.ok) throw new Error(data.error || (response.status === 403 ? 'Unable to add this item. Refresh the page and try again.' : 'Unable to add this item. Please try again.'));
            if (typeof data.created !== 'boolean' || !Number.isInteger(data.cart_count)) throw new Error('Unable to confirm the cart update. Please try again.');
            window.YellovedToast.show({title: 'Cart', message: data.created ? 'Added to your cart' : 'This item is already in your cart', type: data.created ? 'success' : 'info'});
            const cart = document.querySelector('.site-header .nav-cart-link');
            if (cart) {
                cart.title = `Cart (${data.cart_count})`;
                cart.setAttribute('aria-label', `Cart, ${data.cart_count} items`);
                let badge = cart.querySelector('.nav-cart-count');
                if (!badge && data.cart_count > 0) {
                    badge = document.createElement('span'); badge.className = 'nav-cart-count';
                    badge.setAttribute('aria-hidden', 'true'); cart.append(badge);
                }
                if (badge) { badge.textContent = data.cart_count; badge.hidden = !data.cart_count; }
            }
        } catch (error) {
            window.YellovedToast.show({title: 'Cart', message: error instanceof TypeError ? 'Unable to add this item. Check your connection and try again.' : (error.message || 'Unable to add this item. Please try again.'), type: 'error'});
        } finally { pending = false; button.disabled = false; }
    });
})();
