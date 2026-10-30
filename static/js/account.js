/* AJAX profile actions reuse Django forms and the global toaster. */
(() => {
    const pageSelector = 'main.profile-page, main.public-profile-page';
    const pending = new WeakSet();
    const guardedForms = '[data-payment-api-form], .security-password-form';
    const syncSubmit = form => {
        if (!form?.matches(guardedForms)) return;
        const fields = [...form.elements].filter(field => field.willValidate);
        const valid = fields.every(field => field.validity.valid && (!field.required || field.value.trim()));
        const passwordsMatch = !form.matches('.security-password-form') ||
            form.elements.new_password1.value === form.elements.new_password2.value;
        form.querySelectorAll('button[type="submit"]').forEach(button => {
            button.disabled = !valid || !passwordsMatch || pending.has(form) || form.dataset.saved === 'true';
        });
    };
    let navigation = 0;
    const show = (message, type = 'error') => window.YellovedToast?.show({
        title: type === 'error' ? 'Please check your details' : 'Success', message, type,
    });
    const csrfToken = form => form.elements.namedItem('csrfmiddlewaretoken')?.value ||
        decodeURIComponent(document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '');
    const payloadFromForm = form => {
        const payload = {};
        for (const field of form.elements) {
            if (!field.name || field.name === 'csrfmiddlewaretoken' || field.disabled ||
                ['submit', 'button', 'reset', 'file'].includes(field.type)) continue;
            if (field.type === 'checkbox') payload[field.name] = field.checked;
            else if (field.type === 'radio') { if (field.checked) payload[field.name] = field.value; }
            else payload[field.name] = field.value;
        }
        return payload;
    };
    const showApiErrors = (form, errors = {}) => {
        const summaries = [];
        for (const [name, values] of Object.entries(errors)) {
            const messages = Array.isArray(values) ? values : [String(values)];
            const field = form.elements.namedItem(name);
            const target = field?.length && !field.tagName ? field[0] : field;
            const wrapper = target?.closest('.biodata-field, .address-form-field, .security-field, .notification-option');
            messages.forEach(message => {
                summaries.push(`${wrapper?.querySelector('label')?.textContent.trim() || ''}${wrapper ? ': ' : ''}${message}`);
                if (wrapper) {
                    const error = document.createElement('small');
                    error.className = 'form-error';
                    error.dataset.accountError = '';
                    error.textContent = message;
                    wrapper.append(error);
                    target.setAttribute('aria-invalid', 'true');
                }
            });
        }
        if (summaries.length) show([...new Set(summaries)].slice(0, 3).join(' '));
        return summaries.length > 0;
    };
    const formErrors = (doc, form) => {
        const errors = [...doc.querySelectorAll('.form-error')].filter(node => !node.hidden && node.textContent.trim());
        const summaries = [];
        for (const error of errors) {
            const wrapper = error.closest('.biodata-field, .address-form-field, .security-field, .form-field');
            const source = wrapper?.querySelector('input, select, textarea');
            const target = source?.name ? form.elements.namedItem(source.name) : null;
            const label = wrapper?.querySelector('label')?.textContent.trim();
            summaries.push((label ? label + ': ' : '') + error.textContent.trim());
            const node = document.createElement('small');
            node.className = 'form-error';
            node.dataset.accountError = '';
            node.textContent = error.textContent.trim();
            if (target) {
                target.setAttribute('aria-invalid', 'true');
                target.closest('.biodata-field, .address-form-field, .security-field, .form-field')?.append(node);
            }
        }
        if (summaries.length) show([...new Set(summaries)].slice(0, 3).join(' '));
        return errors.length > 0;
    };
    const initPhoto = root => {
    const input = root.querySelector('.profile-photo-input');
    if (!input) return;
    const preview = root.querySelector('.biodata-photo-placeholder img');
    const original = preview?.getAttribute('src');
    const hint = root.querySelector('[data-profile-photo-feedback]');
    let previewUrl, generation = 0;
    const fail = message => {
        input.value = '';
        input.setAttribute('aria-invalid', 'true');
        if (hint) { hint.textContent = message; hint.classList.add('photo-error'); }
        if (preview && original) preview.src = original;
        show(message);
    };
    input.addEventListener('change', async () => {
        const current = ++generation;
        const file = input.files[0];
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        input.removeAttribute('aria-invalid');
        if (!file) return;
        if (file.size > 5 * 1024 * 1024) { fail('Your photo must be 5 MB or smaller.'); return; }
        if (!['image/jpeg', 'image/png', 'image/gif', 'image/webp'].includes(file.type)) {
            fail('Choose a JPG, PNG, GIF, or WEBP image.'); return;
        }
        const url = URL.createObjectURL(file);
        const image = new Image();
        image.src = url;
        try {
            await image.decode();
            if (current !== generation) { URL.revokeObjectURL(url); return; }
            if (Math.max(image.naturalWidth, image.naturalHeight) > 4096) {
                URL.revokeObjectURL(url); fail('Your photo must be 4096 × 4096 pixels or smaller.'); return;
            }
            previewUrl = url;
            if (preview) preview.src = url;
            if (hint) { hint.textContent = `${file.name} · Ready to save`; hint.classList.remove('photo-error'); }
        } catch (_) {
            URL.revokeObjectURL(url);
            if (current === generation) fail('This photo could not be read. Please choose another image.');
        }
    });

    };
    const init = root => {
        initPhoto(root);
        root.querySelectorAll(guardedForms).forEach(syncSubmit);
        root.querySelectorAll('.form-error').forEach(node => {
            if (node.textContent.trim() && !node.hidden) show(node.textContent.trim());
        });
    };
    const mount = (html, url, push = false) => {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        const incoming = doc.querySelector(pageSelector);
        const current = document.querySelector(pageSelector);
        if (!incoming || !current) throw new Error('Your session may have expired. Please sign in again; your details have been kept.');
        const next = document.importNode(incoming, true);
        current.replaceWith(next);
        // Keep the shared avatar in sync after an AJAX photo change.
        for (const selector of ['.nav-profile-trigger img', '.profile-dropdown-heading > img']) {
            const image = document.querySelector(selector);
            const source = doc.querySelector(selector)?.getAttribute('src');
            if (image && source) { image.hidden = false; image.src = source; }
        }
        document.title = doc.title;
        if (push) history.pushState({}, '', url);
        else history.replaceState({}, '', url);
        init(next);
    };
    const load = async (url, push = false) => {
        const version = ++navigation;
        const response = await fetch(url, {credentials: 'same-origin', headers: {Accept: 'text/html'}});
        if (!response.ok) throw new Error('Unable to load this page. Please try again.');
        const html = await response.text();
        if (version === navigation) mount(html, response.url, push);
    };
    document.addEventListener('submit', async event => {
        const form = event.target;
        if (!form.closest('.profile-page') || form.closest('.profile-logout')) return;
        if ((form.method || 'get').toLowerCase() === 'get') {
            event.preventDefault();
            const url = new URL(form.action);
            new FormData(form).forEach((value, key) => url.searchParams.set(key, value));
            try { await load(url, true); } catch (error) { show(error.message); }
            return;
        }
        event.preventDefault();
        if (pending.has(form) || !form.reportValidity()) return;
        pending.add(form);
        const navigationAtSubmit = navigation;
        form.querySelectorAll('[data-account-error], .form-error').forEach(node => node.remove());
        form.querySelectorAll('[aria-invalid]').forEach(node => node.removeAttribute('aria-invalid'));
        const body = new FormData(form);
        const buttons = [...form.querySelectorAll('button[type="submit"]')];
        buttons.forEach(button => { button.disabled = true; });
        form.setAttribute('aria-busy', 'true');
        let saved = false;
        try {
            if (form.dataset.apiUrl) {
                const method = (form.dataset.apiMethod || 'POST').toUpperCase();
                const hasFile = [...form.elements].some(field => field.type === 'file' && field.files?.length);
                const headers = {Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': csrfToken(form)};
                const options = {method, credentials: 'same-origin', headers};
                if (!['GET', 'HEAD', 'DELETE'].includes(method)) {
                    if (hasFile) options.body = new FormData(form);
                    else {
                        headers['Content-Type'] = 'application/json';
                        options.body = JSON.stringify(payloadFromForm(form));
                    }
                }
                const response = await fetch(form.dataset.apiUrl, options);
                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    if (data.errors && showApiErrors(form, data.errors)) return;
                    throw new Error(data.error || 'Unable to save. Please try again.');
                }
                saved = true;
                if (form.dataset.successUrl && form.isConnected && navigation === navigationAtSubmit) {
                    await load(form.dataset.successUrl);
                }
                show(data.message || 'Changes saved successfully.', 'success');
                return;
            }
            const response = await fetch(form.action, {method: 'POST', body, credentials: 'same-origin',
                headers: {Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest'}});
            if (response.redirected) throw new Error('Your session may have expired. Please sign in again; your details have been kept.');
            if ((response.headers.get('Content-Type') || '').includes('application/json')) {
                const data = await response.json();
                if (!response.ok || !data.url) throw new Error(data.error || 'Unable to save. Please try again.');
                saved = true;
                if (!form.isConnected || navigation !== navigationAtSubmit) { show(data.message, 'success'); return; }
                await load(data.url);
                show(data.message, 'success');
            } else {
                const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
                if (!formErrors(doc, form)) throw new Error('Unable to complete this action. Your details have been kept; please retry.');
            }
        } catch (error) {
            show(saved ? 'Your changes were saved, but the page could not refresh. Reload before making another change.' : error.message);
            if (saved) form.dataset.saved = 'true';
        } finally {
            pending.delete(form);
            form.removeAttribute('aria-busy');
            buttons.forEach(button => { button.disabled = form.dataset.saved === 'true'; });
            syncSubmit(form);
        }
    });
    document.addEventListener('click', async event => {
        if (event.target.closest('.address-search-clear')) {
            const input = document.getElementById('address-search');
            input.value = '';
            input.dispatchEvent(new Event('input', {bubbles: true}));
            input.focus();
            return;
        }
        const toggle = event.target.closest('#toggle-address-form');
        if (toggle) {
            event.preventDefault();
            const section = document.getElementById('address-form');
            if (!section) return;
            section.hidden = !section.hidden;
            toggle.setAttribute('aria-expanded', String(!section.hidden));
            toggle.textContent = section.hidden ? '+ Add address' : 'Close form';
            return;
        }
        const link = event.target.closest('a[href]');
        if (!link || !link.closest(pageSelector) || link.target || event.defaultPrevented ||
            event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        const url = new URL(link.href);
        if (url.origin !== location.origin || !url.pathname.startsWith('/account/')) return;
        if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
        event.preventDefault();
        try { await load(url, true); window.scrollTo({top: 0, behavior: 'instant'}); }
        catch (error) { show(error.message); }
    });
    document.addEventListener('input', event => {
        syncSubmit(event.target.form);
        if (event.target.id !== 'address-search') return;
        const query = event.target.value.trim().toLocaleLowerCase();
        event.target.closest('.address-search-box').querySelector('.address-search-clear').hidden = !event.target.value;
        document.querySelectorAll('.saved-address-card').forEach(card => { card.hidden = !card.dataset.search.includes(query); });
    });
    document.addEventListener('change', event => {
        syncSubmit(event.target.form);
        if (!event.target.matches('.reviews-period select')) return;
        event.target.form.requestSubmit();
    });
    let lastInvalid = 0;
    document.addEventListener('invalid', event => {
        if (!event.target.closest('.profile-page, .auth-page') || Date.now() - lastInvalid < 1500) return;
        lastInvalid = Date.now();
        const label = event.target.labels?.[0]?.textContent.trim() || 'This field';
        show(label + ': ' + event.target.validationMessage);
    }, true);
    window.addEventListener('popstate', () => {
        if (document.querySelector(pageSelector)) load(location.href).catch(error => show(error.message));
    });
    init(document);
})();
