/* Browser-local, account/recipient-scoped drafts including attachment Files. */
(() => {
    const transact = (key, value, expected) => new Promise((resolve, reject) => {
        let db, tx, finished = false;
        const finish = (error, result) => {
            if (finished) return; finished = true; clearTimeout(timer);
            if (error) {try {tx?.abort();} catch (_) {}}
            db?.close(); error ? reject(error) : resolve(result);
        };
        const timer = setTimeout(() => finish(new Error('Draft storage timed out.')), 5000);
        let open;
        try {open = indexedDB.open('yelloved-chat-drafts', 1);} catch (error) {finish(error); return;}
        open.onupgradeneeded = () => open.result.createObjectStore('drafts');
        open.onerror = () => finish(open.error);
        open.onblocked = () => finish(new Error('Draft storage is blocked.'));
        open.onsuccess = () => {
            db = open.result;
            if (finished) {db.close(); return;}
            try {
                tx = db.transaction('drafts', value === undefined ? 'readonly' : 'readwrite');
                const store = tx.objectStore('drafts'), read = store.get(key);
                let result, failure;
                read.onsuccess = () => {
                    try {
                        if (value === undefined) {result = read.result; return;}
                        if ((read.result?.revision || null) !== expected) {
                            failure = new Error('This chat draft changed in another tab. Your current text is kept here; reload after copying it to review the saved draft.');
                            tx.abort(); return;
                        }
                        result = {revision: crypto.randomUUID(), data: value}; store.put(result, key);
                    } catch (error) {failure = error; tx.abort();}
                };
                tx.oncomplete = () => finish(null, result);
                tx.onerror = tx.onabort = () => finish(failure || tx.error || new Error('Unable to save draft.'));
            } catch (error) {finish(error);}
        };
    });
    const create = ({owner, peer, snapshot, restore, onError}) => {
        const key = `${owner}:${peer}`;
        let revision = null, generation = 0, dirty = false, stopped = false, timer, warned = false;
        let chain = Promise.resolve();
        const report = error => {if (!warned && !stopped) {warned = true; onError(error.message);}};
        const ready = transact(key).then(record => {
            if (stopped) return;
            revision = record?.revision || null;
            if (record?.data) restore(record.data);
        }).catch(report);
        const save = () => {
            const version = ++generation; dirty = true; clearTimeout(timer);
            chain = chain.catch(() => {}).then(async () => {
                await ready;
                if (stopped) return false;
                const result = await transact(key, snapshot(), revision);
                revision = result.revision;
                if (version === generation) dirty = false;
                return true;
            }).catch(error => {report(error); return false;});
            return chain;
        };
        return {ready, save, schedule() {dirty = true; ++generation; clearTimeout(timer); timer = setTimeout(save, 250);},
            get dirty() {return dirty;}, stop() {stopped = true; clearTimeout(timer);}};
    };
    window.YellovedChatDrafts = {create, read: key => transact(key), write: (key, value, revision) => transact(key, value, revision)};
})();
