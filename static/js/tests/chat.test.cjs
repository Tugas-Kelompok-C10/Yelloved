const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {randomUUID} = require('node:crypto');

class Element {
    constructor() {this.children = []; this.dataset = {}; this.handlers = {}; this.value = ''; this.scrollHeight = 100; this.scrollTop = 0; this.clientHeight = 400;}
    append(...nodes) {this.children.push(...nodes);}
    replaceChildren(...nodes) {this.children = nodes;}
    addEventListener(name, fn) {this.handlers[name] = fn;}
    querySelector(selector) {return this.selectors?.[selector];}
    setAttribute() {}
    reportValidity() {return true;}
    focus() {}
    showModal() {this.open = true;}
    close() {this.open = false;}
    get textContent() {return [this.text || '', ...this.children.map(child => child.textContent)].join(' ');}
    set textContent(text) {this.text = text; this.children = [];}
}
const response = (status, data) => ({ok: status < 400, status, headers: {get: () => 'application/json'}, json: async () => data});
const flush = () => new Promise(resolve => setImmediate(resolve));
const original = {id: randomUUID(), body: 'Original', mine: true, deleted: false, created_at: new Date().toISOString(),
    revision: 'v1', edit_url: '/edit/', delete_url: '/delete/'};

function harness(initial = [], getResult) {
    const list = new Element(), compose = new Element(), input = new Element(), submit = new Element();
    compose.elements = {body: input}; compose.selectors = {'[type=submit]': submit, '[name=csrfmiddlewaretoken]': {value: 'csrf'}};
    const app = new Element(), dialog = new Element(), actionForm = new Element();
    app.dataset = {messagesUrl: '/messages/', inboxUrl: '/inbox/', peerId: '2'};
    app.selectors = {'[data-chat-messages]': list, '[data-chat-compose]': compose, '[data-chat-status]': new Element(),
        '[data-chat-older]': new Element(), '[data-chat-threads]': new Element(), '[data-chat-more-threads]': new Element()};
    dialog.selectors = Object.fromEntries(['[data-chat-cancel]', '[data-chat-dialog-title]', '[data-chat-edit-fields]',
        '[data-chat-delete-text]', '[data-chat-confirm]'].map(selector => [selector, new Element()]));
    dialog.selectors.form = actionForm; actionForm.elements = {body: new Element()};
    const calls = [], notifications = [], gets = [];
    const events = {};
    const fakeFetch = async (url, options) => {
        if (options.method === 'GET') {
            gets.push(String(url));
            const result = getResult?.(new URL(url, 'https://local.test'));
            return response(200, result || (String(url).includes('/messages/') ? {messages: initial, has_older: false, sync_cursor: 0} : {conversations: []}));
        }
        return new Promise(resolve => calls.push({data: options.body, resolve}));
    };
    const window = {addEventListener(name, fn) {events[name] = fn;}, YellovedToast: {show: value => notifications.push(value)},
        YellovedChatHTTP: {userId: '1', identity: 'session-a', request: async (url, data) => {
            const result = await fakeFetch(url, {method: data ? 'POST' : 'GET', body: data});
            const json = await result.json();
            if (!result.ok) throw new Error(json.message);
            return json;
        }}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'chat.js'), 'utf8'), {
        window, location: {origin: 'https://local.test'}, URL, FormData, crypto: {randomUUID},
        setTimeout: () => 1, clearTimeout() {},
        document: {hidden: false, querySelector: selector => selector === '[data-chat-app]' ? app : dialog,
            createElement: () => new Element(), createDocumentFragment: () => new Element()},
    });
    return {list, compose, input, calls, gets, notifications, actionForm, events, app,
        send: text => {input.value = text; compose.handlers.submit({preventDefault() {}});},
        openAction: (action, id = original.id) => app.handlers.click({target: {closest: selector => selector === '[data-chat-action]' ? {dataset: {messageId: id, chatAction: action}} : null}})};
}

test('sending is optimistic; failed requests retain a retryable message and reuse its token', async () => {
    const ui = harness(); await flush();
    ui.send('Hello');
    assert.match(ui.list.textContent, /Sending/);
    assert.equal(ui.input.value, '');
    await flush();
    const token = ui.calls[0].data.get('client_id');
    ui.calls[0].resolve(response(503, {message: 'Offline'})); await flush();
    assert.match(ui.list.textContent, /Not sent/);
    assert.match(ui.list.textContent, /Retry/);
    assert.equal(ui.notifications[0].message, 'Offline');
    assert.equal(ui.calls.length, 1);
    ui.openAction('retry', token);
    await flush();
    assert.equal(ui.calls[1].data.get('client_id'), token);
    ui.calls[1].resolve(response(201, {entry: {...original, id: token, body: 'Hello'}})); await flush();
    assert.doesNotMatch(ui.list.textContent, /Not sent/);
});

test('account/session changes clear private UI and ignore a late send response', async () => {
    const ui = harness([original]); await flush();
    ui.send('Private pending message');
    await flush();
    ui.events['chat:session-ended']({detail: {message: 'Account changed'}});
    assert.equal(ui.input.value, '');
    assert.doesNotMatch(ui.app.textContent, /Original|Private pending/);
    assert.match(ui.app.textContent, /Reload Chat/);
    ui.calls[0].resolve(response(201, {entry: {...original, body: 'Late response'}})); await flush();
    assert.doesNotMatch(ui.app.textContent, /Late response/);
});

test('failed optimistic edit restores the original message', async () => {
    const ui = harness([original]); await flush();
    ui.openAction('edit'); ui.actionForm.elements.body.value = 'Changed';
    const saving = ui.actionForm.handlers.submit({preventDefault() {}});
    assert.match(ui.list.textContent, /Changed/);
    assert.match(ui.list.textContent, /Saving/);
    ui.calls[0].resolve(response(409, {message: 'Changed in another tab'}));
    await saving;
    assert.match(ui.list.textContent, /Original/);
    assert.equal(ui.notifications[0].message, 'Changed in another tab');
});

test('optimistic delete is confirmed asynchronously', async () => {
    const ui = harness([original]); await flush();
    ui.openAction('delete');
    const saving = ui.actionForm.handlers.submit({preventDefault() {}});
    assert.match(ui.list.textContent, /Message deleted/);
    ui.calls[0].resolve(response(200, {entry: {...original, body: '', deleted: true, revision: 'v2'}, message: 'Message deleted.'}));
    await saving;
    assert.equal(ui.notifications[0].type, 'success');
    assert.match(ui.list.textContent, /Message deleted/);
});

test('polling drains change batches and does not insert unloaded old edits', async () => {
    const recent = {...original, version: 60, created_version: 60};
    const next = {...original, id: randomUUID(), body: 'New incoming', version: 161, created_version: 161};
    const old = {...original, id: randomUUID(), body: 'Unloaded old edit', version: 162, created_version: 1};
    const ui = harness([], url => {
        if (!url.pathname.includes('/messages/')) return {conversations: []};
        if (!url.searchParams.has('after')) return {messages: [recent], sync_cursor: 60, has_older: true};
        if (url.searchParams.get('after') === '60') return {messages: [next, old], sync_cursor: 162, has_more_changes: true};
        return {messages: [{...next, deleted: true, body: '', version: 163, revision: 'v2'}], sync_cursor: 163, has_more_changes: false};
    });
    await flush(); ui.events.focus(); await flush();
    assert.match(ui.list.textContent, /Message deleted/);
    assert.doesNotMatch(ui.list.textContent, /Unloaded old edit|New incoming/);
    assert.ok(ui.gets.some(url => url.includes('after=162')));
    assert.equal(ui.app.selectors['[data-chat-older]'].hidden, false);
});

test('conversation pages remain visible after polling refreshes the inbox', async () => {
    const row = id => ({peer_id: id, name: `Person ${id}`, preview: 'Hello', url: `/chat/with/${id}/`});
    const ui = harness([], url => {
        if (url.pathname === '/inbox/') return url.searchParams.has('cursor')
            ? {conversations: [row(52)], next_cursor: null} : {conversations: [row(2)], next_cursor: 'page-two'};
        return {messages: [], sync_cursor: 0, has_older: false};
    });
    await flush();
    const control = ui.app.selectors['[data-chat-more-threads]'];
    assert.equal(control.hidden, false);
    ui.app.handlers.click({target: {closest: selector => selector === '[data-chat-more-threads]' ? control : null}});
    await flush(); ui.events.focus(); await flush();
    const text = ui.app.selectors['[data-chat-threads]'].textContent;
    assert.match(text, /Person 2/); assert.match(text, /Person 52/);
    assert.equal(control.hidden, true);
});

test('retrying an already-delivered older message does not skip unloaded history', async () => {
    const ui = harness([], url => url.pathname === '/messages/'
        ? {messages: [], sync_cursor: 100, has_older: true} : {conversations: []});
    await flush(); ui.send('Retry me'); await flush();
    const token = ui.calls[0].data.get('client_id');
    ui.calls[0].resolve(response(200, {entry: {...original, id: token, body: 'Old delivered message', created_version: 2}}));
    await flush();
    assert.doesNotMatch(ui.list.textContent, /Old delivered message|Not sent/);
    assert.match(ui.notifications[0].message, /already delivered/);
    assert.equal(ui.app.selectors['[data-chat-older]'].hidden, false);
});
