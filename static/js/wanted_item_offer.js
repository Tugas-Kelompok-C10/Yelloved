(() => {
    let modal = document.getElementById('item-offer-modal');
    const bound = new WeakSet();
    const states = new Map();
    let activeForm, guard = false, leaving = false, asking = false;
    const notify = (message, type = 'success') => window.YellovedToast?.show({title: type === 'error' ? 'Unable to save draft' : 'Offer draft', message, type});
    // IndexedDB preserves photos together with text, separately for each account/post.
    const storage = (mode, key, value, revision = null) => new Promise((resolve, reject) => {
        const request = indexedDB.open('yelloved-offer-drafts', 1);
        request.onupgradeneeded = () => request.result.createObjectStore('drafts');
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            const db = request.result;
            const tx = db.transaction('drafts', mode === 'get' ? 'readonly' : 'readwrite');
            const store = tx.objectStore('drafts');
            let result, conflict;
            const operation = store.get(key);
            operation.onsuccess = () => {
                const current = operation.result;
                if (mode === 'get') { result = current; return; }
                // The compare and write share an IndexedDB readwrite transaction,
                // so two tabs cannot both overwrite the same draft revision.
                if ((current?.revision || null) !== revision) {
                    conflict = new Error('This draft changed in another tab. Your edits are still here. Reopen this offer to load the latest draft before saving or discarding.');
                    tx.abort();
                    return;
                }
                result = {revision: crypto.randomUUID(), deleted: mode === 'delete', data: mode === 'put' ? value : null};
                store.put(result, key);
            };
            tx.oncomplete = () => { db.close(); resolve(result); };
            tx.onabort = tx.onerror = () => { db.close(); reject(conflict || tx.error); };
        };
    });
    window.YellovedWantedDraftStore = {storage};
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
        const state = {dirty: false, revision: null};
        states.set(form, state);
        try {
            const entry = await storage('get', postKey(form));
            if (states.get(form) !== state) return;
            state.revision = entry?.revision || null;
            const draft = entry?.deleted ? null : (entry?.data || entry);
            if (!draft || state.dirty) return;
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
    const exit = async (form, done, navigating = false) => {
        if (asking) return;
        if (!isDirty(form)) { done(); return; }
        asking = true;
        try {
            const choice = await ask();
            if (choice === 'stay') return;
            const state = states.get(form);
            await state.ready;
            const saved = await storage(choice === 'save' ? 'put' : 'delete', postKey(form), snapshot(form), state.revision);
            state.revision = saved.revision;
            state.dirty = false;
            if (choice === 'discard') form.reset();
            const message = choice === 'save' ? 'Draft saved on this browser.' : 'Draft discarded.';
            if (navigating) window.YellovedToast?.queue({title: 'Offer draft', message, type: 'success'});
            done();
            if (!navigating) notify(message);
        } catch (error) {
            notify(error.message?.startsWith('This draft changed') ? error.message
                : 'Browser storage is unavailable. Your draft is still here; please retry.', 'error');
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
            const ready = restore(form);
            states.get(form).ready = ready;
            modal.showModal();
        }
        if (event.target.closest('[data-close-item-offer-modal]')) closeModal();
        const link = event.target.closest('a[href]');
        if (link && !event.defaultPrevented && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && !link.target && isDirty(activeForm)) {
            event.preventDefault();
            exit(activeForm, () => { leaving = true; location.assign(link.href); }, true);
        }
    });
    const init = () => {
    modal = document.getElementById('item-offer-modal');
    if (modal && !bound.has(modal)) {
        bound.add(modal);
        modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
        modal.addEventListener('cancel', event => { event.preventDefault(); closeModal(); });
    }
    document.querySelectorAll('[data-item-offer-form]').forEach(form => {
        if (bound.has(form)) return;
        bound.add(form);
        states.set(form, {dirty: false, revision: null});
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
        if (!form.closest('dialog')) {
            const ready = restore(form);
            states.get(form).ready = ready;
        }
    });
    };
    window.addEventListener('wanted:mounted', init);
    init();
    window.addEventListener('popstate', () => {
        if (!guard || leaving) return;
        guard = false;
        if (!isDirty(activeForm)) { leaving = true; history.back(); return; }
        protectBack();
        exit(activeForm, () => { leaving = true; history.go(-2); }, true);
    });
    window.addEventListener('beforeunload', event => {
        if (!leaving && isDirty(activeForm)) { event.preventDefault(); event.returnValue = ''; }
    });
})();
