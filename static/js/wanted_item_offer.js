(() => {
    const forms = [...document.querySelectorAll('[data-item-offer-form]')];
    if (!forms.length) return;
    const modal = document.getElementById('item-offer-modal');
    const states = new Map();
    let activeForm, guard = false, leaving = false, asking = false;
    const notify = (message, type = 'success') => window.YellovedToast?.show({title: type === 'error' ? 'Unable to save draft' : 'Offer draft', message, type});
    // IndexedDB preserves photos together with text, separately for each account/post.
    const storage = (mode, key, value) => new Promise((resolve, reject) => {
        const request = indexedDB.open('yelloved-offer-drafts', 1);
        request.onupgradeneeded = () => request.result.createObjectStore('drafts');
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            const db = request.result;
            const tx = db.transaction('drafts', mode === 'get' ? 'readonly' : 'readwrite');
            const store = tx.objectStore('drafts');
            const operation = mode === 'get' ? store.get(key) : mode === 'put' ? store.put(value, key) : store.delete(key);
            tx.oncomplete = () => { db.close(); resolve(operation.result); };
            tx.onabort = tx.onerror = () => { db.close(); reject(tx.error); };
        };
    });
    const postKey = form => `${form.dataset.draftUser}:${form.elements.wanted_post.value.split('/').filter(Boolean).at(-1)}`;
    const snapshot = form => ({price: form.elements.price.value, description: form.elements.description.value, image: form.elements.image.files[0] || null});
    const hasContent = form => { const d = snapshot(form); return Boolean(d.price || d.description.trim() || d.image); };
    const isDirty = form => Boolean(form && states.get(form)?.dirty && hasContent(form));
    const protectBack = () => {
        if (!guard) { history.pushState({wantedOfferDraft: true}, '', location.href); guard = true; }
    };
    const update = form => {
        const message = form.elements.description;
        message.setCustomValidity(message.value.trim() ? '' : 'Describe your item and pickup location.');
        form.querySelector('[data-send-item-offer]').disabled = form.querySelector('fieldset').disabled || !form.checkValidity();
    };
    const restore = async form => {
        const state = {dirty: false};
        states.set(form, state);
        try {
            const draft = await storage('get', postKey(form));
            if (!draft || states.get(form) !== state || state.dirty) return;
            form.elements.price.value = draft.price;
            form.elements.description.value = draft.description;
            if (draft.image) {
                const transfer = new DataTransfer();
                transfer.items.add(draft.image);
                form.elements.image.files = transfer.files;
                form.elements.image.dispatchEvent(new Event('change', {bubbles: true}));
            }
            state.dirty = true;
            activeForm = form;
            update(form);
            protectBack();
            notify('Your saved offer draft has been restored.');
        } catch (_) { /* Form stays usable when storage is unavailable. */ }
    };
    const ask = () => new Promise(resolve => {
        const dialog = document.createElement('dialog');
        dialog.className = 'wanted-modal';
        dialog.innerHTML = '<h2>Save your offer draft?</h2><p>Keep your photo, price, and message on this browser, or discard them.</p><div class="wanted-modal-actions"><button type="button" class="wanted-button wanted-action-offer" data-choice="save">Save draft</button><button type="button" class="wanted-button wanted-action-secondary" data-choice="discard">Discard</button><button type="button" class="wanted-button wanted-action-secondary" data-choice="stay">Keep editing</button></div>';
        document.body.append(dialog);
        const finish = choice => { dialog.close(); dialog.remove(); resolve(choice); };
        dialog.addEventListener('click', event => { if (event.target.dataset.choice) finish(event.target.dataset.choice); });
        dialog.addEventListener('cancel', event => { event.preventDefault(); finish('stay'); });
        dialog.showModal();
    });
    const exit = async (form, done) => {
        if (asking) return;
        if (!isDirty(form)) { done(); return; }
        asking = true;
        try {
            const choice = await ask();
            if (choice === 'stay') return;
            await storage(choice === 'save' ? 'put' : 'delete', postKey(form), snapshot(form));
            states.get(form).dirty = false;
            if (choice === 'discard') form.reset();
            notify(choice === 'save' ? 'Draft saved on this browser.' : 'Draft discarded.');
            done();
        } catch (_) {
            notify('Browser storage is unavailable. Your draft is still here; please retry.', 'error');
        } finally { asking = false; }
    };
    const closeModal = () => exit(modal.querySelector('[data-item-offer-form]'), () => modal.close());
    document.addEventListener('click', event => {
        const trigger = event.target.closest('[data-open-item-offer-modal]');
        if (trigger && modal) {
            const form = modal.querySelector('[data-item-offer-form]');
            form.reset();
            form.elements.wanted_post.value = trigger.dataset.offerPost;
            modal.querySelector('[data-offer-target]').textContent = `${trigger.dataset.offerTitle} · Max budget ${trigger.dataset.offerBudget}`;
            activeForm = form;
            restore(form);
            modal.showModal();
        }
        if (event.target.closest('[data-close-item-offer-modal]')) closeModal();
        const link = event.target.closest('a[href]');
        if (link && !event.defaultPrevented && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && !link.target && isDirty(activeForm)) {
            event.preventDefault();
            exit(activeForm, () => { leaving = true; location.assign(link.href); });
        }
    });
    modal?.addEventListener('click', event => { if (event.target === modal) closeModal(); });
    modal?.addEventListener('cancel', event => { event.preventDefault(); closeModal(); });
    forms.forEach(form => {
        states.set(form, {dirty: false});
        const changed = () => { states.get(form).dirty = true; activeForm = form; update(form); if (hasContent(form)) protectBack(); };
        form.addEventListener('input', changed);
        form.addEventListener('change', changed);
        form.addEventListener('offer-image-validated', () => update(form));
        form.addEventListener('reset', () => {
            form.querySelector('[data-offer-feedback]').textContent = '';
            queueMicrotask(() => update(form));
        });
        form.addEventListener('submit', event => {
            event.preventDefault();
            update(form);
            if (!form.reportValidity() || form.querySelector('[data-send-item-offer]').disabled) return;
            form.querySelector('[data-offer-feedback]').textContent = 'Your offer is ready. Sending offers is not connected yet.';
        });
        update(form);
        if (!form.closest('dialog')) restore(form);
    });
    window.addEventListener('popstate', () => {
        if (!guard || leaving) return;
        guard = false;
        if (!isDirty(activeForm)) { leaving = true; history.back(); return; }
        protectBack();
        exit(activeForm, () => { leaving = true; history.go(-2); });
    });
    window.addEventListener('beforeunload', event => {
        if (!leaving && isDirty(activeForm)) { event.preventDefault(); event.returnValue = ''; }
    });
})();
