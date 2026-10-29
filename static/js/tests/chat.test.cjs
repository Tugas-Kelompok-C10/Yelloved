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

function harness(initial = []) {
    const list = new Element(), compose = new Element(), input = new Element(), submit = new Element();
    compose.elements = {body: input}; compose.selectors = {'[type=submit]': submit, '[name=csrfmiddlewaretoken]': {value: 'csrf'}};
    const app = new Element(), dialog = new Element(), actionForm = new Element();
    app.dataset = {messagesUrl: '/messages/', inboxUrl: '/inbox/', peerId: '2'};
    app.selectors = {'[data-chat-messages]': list, '[data-chat-compose]': compose, '[data-chat-status]': new Element(),
        '[data-chat-older]': new Element(), '[data-chat-threads]': new Element()};
    dialog.selectors = Object.fromEntries(['[data-chat-cancel]', '[data-chat-dialog-title]', '[data-chat-edit-fields]',
        '[data-chat-delete-text]', '[data-chat-confirm]'].map(selector => [selector, new Element()]));
    dialog.selectors.form = actionForm; actionForm.elements = {body: new Element()};
    const calls = [], notifications = [];
    const events = {};
    const fakeFetch = async (url, options) => {
        if (options.method === 'GET') return response(200, String(url).includes('/messages/') ? {messages: initial, has_older: false} : {conversations: []});
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
    return {list, compose, input, calls, notifications, actionForm, events, app,
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
