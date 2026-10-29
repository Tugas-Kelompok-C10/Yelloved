const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');

// Model IndexedDB's serialized readwrite transactions, shared by two tabs.
function database() {
    const records = new Map();
    let tail = Promise.resolve();
    const db = {close() {}, transaction() {
        let release;
        const previous = tail;
        tail = new Promise(resolve => {release = resolve;});
        const tx = {objectStore: () => ({
            get(key) {
                const request = {};
                previous.then(() => {
                    request.result = records.get(key);
                    request.onsuccess();
                    queueMicrotask(() => {if (!tx.aborted) {tx.oncomplete(); release();}});
                });
                return request;
            },
            put(value, key) {records.set(key, value);},
        }), abort() {tx.aborted = true; queueMicrotask(() => {tx.onabort(); release();});}};
        return tx;
    }};
    return {open() {const request = {result: db}; queueMicrotask(() => request.onsuccess()); return request;}};
}
function tab(indexedDB) {
    const window = {addEventListener() {}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'wanted_item_offer.js'), 'utf8'), {
        window, indexedDB, crypto: {randomUUID}, setTimeout, clearTimeout,
        document: {getElementById: () => null, querySelectorAll: () => [], addEventListener() {}},
    });
    const store = window.YellovedWantedDraftStore;
    return Object.assign(store.storage, {discard: store.discard, isDiscarded: store.isDiscarded});
}

test('two tabs cannot overwrite the same draft revision', async () => {
    const db = database(), a = tab(db), b = tab(db);
    const [left, right] = await Promise.all([a('get', 'post'), b('get', 'post')]);
    assert.equal(left, undefined);
    assert.equal(right, undefined);
    const results = await Promise.allSettled([
        a('put', 'post', {price: '100000'}, null), b('put', 'post', {price: '120000'}, null),
    ]);
    assert.equal(results.filter(result => result.status === 'fulfilled').length, 1);
    assert.match(results.find(result => result.status === 'rejected').reason.message, /another tab/);
    assert.equal((await a('get', 'post')).data.price, '100000');
});

test('discarding retains a revision so a stale tab cannot resurrect the draft', async () => {
    const db = database(), a = tab(db), b = tab(db);
    const initial = await a('put', 'post', {price: '100000'}, null);
    await b('delete', 'post', null, initial.revision);
    await assert.rejects(a('put', 'post', {price: '120000'}, initial.revision), /another tab/);
    assert.equal((await a('get', 'post')).deleted, true);
});

test('discard remains possible when IndexedDB and localStorage are unavailable', async () => {
    const store = tab({open() {throw new Error('Storage disabled');}});
    assert.equal((await store.discard('post', null)).removed, false);
    assert.equal(store.isDiscarded('post'), true);
});

test('discarding local edits keeps a newer draft from another tab and still permits leaving', async () => {
    const db = database(), a = tab(db), b = tab(db);
    const first = await a('put', 'post', {price: '100000'}, null);
    await b('put', 'post', {price: '120000'}, first.revision);
    const result = await a.discard('post', first.revision);
    assert.equal(result.newer, true);
    assert.equal((await b('get', 'post')).data.price, '120000');
});
