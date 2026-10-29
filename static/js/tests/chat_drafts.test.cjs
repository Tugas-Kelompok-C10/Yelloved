const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');
const script = fs.readFileSync(path.join(__dirname, '..', 'chat_drafts.js'), 'utf8');

function database() {
    const records = new Map(); let tail = Promise.resolve();
    const db = {close() {}, transaction() {
        let release; const previous = tail; tail = new Promise(resolve => {release = resolve;});
        const tx = {objectStore: () => ({get(key) {
            const request = {}; previous.then(() => {request.result = records.get(key); request.onsuccess();
                queueMicrotask(() => {if (!tx.aborted) {tx.oncomplete(); release();}});}); return request;
        }, put(value, key) {records.set(key, structuredClone(value));}}),
        abort() {tx.aborted = true; queueMicrotask(() => {tx.onabort(); release();});}};
        return tx;
    }};
    return {open() {const request = {result: db}; queueMicrotask(() => request.onsuccess()); return request;}};
}
function store(indexedDB) {
    const window = {};
    vm.runInNewContext(script, {window, indexedDB, crypto: {randomUUID}, setTimeout, clearTimeout});
    return window.YellovedChatDrafts;
}

test('drafts preserve text, attachments and retry tokens across page instances', async () => {
    const db = database(), api = store(db), file = new Blob(['attachment']);
    const saved = {composer: {body: 'Unsent text', file}, outgoing: [{id: 'same-retry-token', body: 'Failed message', file, state: 'failed'}]};
    const first = api.create({owner: 'alice', peer: 'bob', snapshot: () => saved, restore() {}, onError: assert.fail});
    await first.ready; await first.save();
    let restored;
    const second = api.create({owner: 'alice', peer: 'bob', snapshot: () => ({}), restore: data => {restored = data;}, onError: assert.fail});
    await second.ready;
    assert.equal(restored.composer.body, 'Unsent text');
    assert.equal(await restored.composer.file.text(), 'attachment');
    assert.equal(restored.outgoing[0].id, 'same-retry-token');
    let leaked = false;
    const different = api.create({owner: 'eve', peer: 'bob', snapshot: () => ({}), restore() {leaked = true;}, onError: assert.fail});
    await different.ready; assert.equal(leaked, false);
});

test('another tab cannot silently overwrite a newer draft', async () => {
    const db = database(), api = store(db), errors = [];
    const options = {owner: 'alice', peer: 'bob', snapshot: () => ({composer: {body: 'Text'}}), restore() {}, onError: message => errors.push(message)};
    const first = api.create(options), second = api.create(options);
    await Promise.all([first.ready, second.ready]);
    assert.equal(await first.save(), true);
    assert.equal(await second.save(), false);
    assert.equal(second.dirty, true);
    assert.match(errors[0], /another tab/);
});

test('unavailable browser storage retains the unsaved-navigation warning', async () => {
    const api = store({open() {throw new Error('Storage unavailable');}});
    const errors = [];
    const draft = api.create({owner: 'a', peer: 'b', snapshot: () => ({composer: {body: 'Keep me'}}), restore() {}, onError: message => errors.push(message)});
    await draft.ready;
    assert.equal(await draft.save(), false);
    assert.equal(draft.dirty, true);
    assert.equal(errors.length, 1);
});
