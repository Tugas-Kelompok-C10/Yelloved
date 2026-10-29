(() => {
    let modal = document.getElementById('item-offer-modal');
    const bound = new WeakSet();
    const states = new Map();
    const discarded = new Set();
    const discardKey = key => `wanted-offer-discarded:${key}`;
    const clearDiscard = key => {discarded.delete(key); try {localStorage.removeItem(discardKey(key));} catch (_) {}};
    const isDiscarded = key => {try {return discarded.has(key) || localStorage.getItem(discardKey(key)) === '1';} catch (_) {return discarded.has(key);}};
    let activeForm, guard = false, leaving = false, asking = false;
    const notify = (message, type = 'success') => window.YellovedToast?.show({title: type === 'error' ? 'Unable to save draft' : 'Offer draft', message, type});
    // IndexedDB preserves photos together with text, separately for each account/post.
    const storage = (mode, key, value, revision = null) => new Promise((resolve, reject) => {
        let completed = false, db, tx;
        const finish = (error, result) => {
            if (completed) return;
            completed = true; clearTimeout(timeout);
            if (error) {try {tx?.abort();} catch (_) {}}
            db?.close();
            if (error) reject(error);
            else {if (mode === 'put') clearDiscard(key); resolve(result);}
        };
        const timeout = setTimeout(() => finish(new Error('Browser storage timed out.')), 5000);
        let request;
        try {request = indexedDB.open('yelloved-offer-drafts', 1);}
        catch (error) {finish(error); return;}
        request.onupgradeneeded = () => request.result.createObjectStore('drafts');
        request.onerror = () => finish(request.error);
        request.onblocked = () => finish(new Error('Browser storage is blocked.'));
        request.onsuccess = () => {
            db = request.result;
            if (completed) {db.close(); return;}
            try {tx = db.transaction('drafts', mode === 'get' ? 'readonly' : 'readwrite');}
            catch (error) {finish(error); return;}
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
            tx.oncomplete = () => finish(null, result);
            tx.onabort = tx.onerror = () => finish(conflict || tx.error || new Error('Browser storage failed.'));
        };
    });
    const discardDraft = async (key, revision) => {
        try {const saved = await storage('delete', key, null, revision); clearDiscard(key); return {removed: true, revision: saved.revision};}
        catch (error) {
            if (error.message?.startsWith('This draft changed')) return {removed: false, newer: true};
            discarded.add(key);
            try {localStorage.setItem(discardKey(key), '1');} catch (_) {}
            return {removed: false, newer: false};
        }
    };
    window.YellovedWantedDraftStore = {storage, discard: discardDraft, isDiscarded};
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
        form.querySelector('[data-send-item-offer]').disabled = Boolean(states.get(form)?.sending) || form.querySelector('fieldset').disabled || !form.checkValidity();
    };
    const restore = async form => {
        const state = {dirty: false, revision: null};
        states.set(form, state);
        try {
            const entry = await storage('get', postKey(form));
            if (states.get(form) !== state) return;
            state.revision = entry?.revision || null;
            const draft = entry?.deleted ? null : (entry?.data || entry);
            if (!draft || state.dirty || isDiscarded(postKey(form))) return;
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
        if (asking || states.get(form)?.sending) return;
        if (!isDirty(form)) { done(); return; }
        asking = true;
        try {
            const choice = await ask();
            if (choice === 'stay') return;
            const state = states.get(form);
            await state.ready;
            let discardedResult = {removed: true};
            if (choice === 'save') {
                const saved = await storage('put', postKey(form), snapshot(form), state.revision);
                state.revision = saved.revision;
            } else discardedResult = await discardDraft(postKey(form), state.revision);
            state.dirty = false;
            if (choice === 'discard') form.reset();
            const message = choice === 'save' ? 'Draft saved on this browser.' : discardedResult.removed ? 'Draft discarded.'
                : discardedResult.newer ? 'Your changes were discarded. A newer draft from another tab was kept.'
                : 'Changes discarded here. Browser storage is unavailable, so a previously saved draft could not be removed.';
            const type = discardedResult.removed || discardedResult.newer ? 'success' : 'error';
            if (navigating) window.YellovedToast?.queue({title: 'Offer draft', message, type});
            done();
            if (!navigating) notify(message, type);
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
            form.elements.submission_id.value = crypto.randomUUID();
            form.elements.wanted_post.value = trigger.dataset.offerPost;
            form.querySelector('[data-offer-chat]').href = trigger.dataset.offerChat;
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
        form.elements.submission_id.value = crypto.randomUUID();
        const changed = () => { states.get(form).dirty = true; activeForm = form; update(form); if (hasContent(form)) protectBack(); };
        form.addEventListener('input', changed);
        form.addEventListener('change', changed);
        form.addEventListener('offer-image-validated', () => update(form));
        form.addEventListener('reset', () => {
            form.querySelector('[data-offer-feedback]').textContent = '';
            queueMicrotask(() => {form.elements.submission_id.value ||= crypto.randomUUID(); update(form);});
        });
        form.addEventListener('submit', async event => {
            event.preventDefault();
            update(form);
            if (!form.reportValidity() || form.querySelector('[data-send-item-offer]').disabled) return;
            const post = form.elements.wanted_post.value.split('/').filter(Boolean).at(-1);
            const feedback = form.querySelector('[data-offer-feedback]');
            if (!/^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(post)) {
                feedback.textContent = 'This is a sample post. Send an offer to a community member’s wanted post instead.'; return;
            }
            const state = states.get(form); state.sending = true; update(form);
            const body = new FormData(form), fieldset = form.querySelector('fieldset');
            fieldset.disabled = true;
            feedback.textContent = 'Sending your offer…';
            const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 15000);
            try {
                const response = await fetch(form.dataset.offerUrlTemplate.replace('00000000-0000-0000-0000-000000000000', post), {
                    method: 'POST', body, signal: controller.signal, credentials: 'same-origin',
                    headers: {'X-CSRFToken': form.elements.csrfmiddlewaretoken.value, 'X-Offer-User': form.dataset.draftUser, Accept: 'application/json'},
                });
                if (!(response.headers.get('Content-Type') || '').includes('application/json')) throw new Error('Unable to send your offer. Please sign in again or retry.');
                const result = await response.json();
                if (!response.ok) throw new Error(result.message || 'Unable to send this offer.');
                await state.ready;
                const discardedDraft = await discardDraft(postKey(form), state.revision);
                state.revision = discardedDraft.revision || null;
                state.dirty = false;
                form.reset();
                if (form.closest('dialog')?.open) form.closest('dialog').close();
                feedback.textContent = result.message;
                window.YellovedToast?.show({title: 'Offer sent', message: result.message, type: 'success'});
                window.dispatchEvent(new Event('activity:changed'));
            } catch (error) {
                feedback.textContent = error.name === 'AbortError' ? 'The request timed out. Retry with this form to confirm your offer without creating a duplicate.' : error.message;
                window.YellovedToast?.show({title: 'Unable to send offer', message: feedback.textContent, type: 'error'});
            } finally {clearTimeout(timeout); state.sending = false; fieldset.disabled = false; update(form);}
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
