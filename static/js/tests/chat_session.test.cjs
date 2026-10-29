const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '..', 'chat_session.js'), 'utf8');

function transport(fetch) {
    const events = [];
    const window = {dispatchEvent: event => events.push(event)};
    vm.runInNewContext(script, {window, AbortController, fetch, CustomEvent: class {constructor(type, options) {this.type = type; this.detail = options.detail;}},
        document: {querySelector: () => ({dataset: {chatSession: 'session-a', chatUser: '1'}})}});
    return {http: window.YellovedChatHTTP, events};
}
const response = (identity, data = {}) => ({status: 200, ok: true,
    headers: {get: name => name === 'X-Chat-Session' ? identity : 'application/json'}, json: async () => data});

test('mismatched session never returns another accounts data and aborts pending requests', async () => {
    let signal, calls = 0;
    const ui = transport(async (_, options) => {signal = options.signal; calls++; return response('session-b', {messages: ['Private']});});
    await assert.rejects(ui.http.request('/messages/'), /session changed/);
    assert.equal(ui.http.blocked, true);
    assert.equal(signal.aborted, true);
    assert.equal(ui.events[0].type, 'chat:session-ended');
    await assert.rejects(ui.http.request('/messages/'), /Reload Chat/);
    assert.equal(calls, 1);
});

test('requests carry the original session identity and CSRF protection', async () => {
    let options;
    const ui = transport(async (_, value) => {options = value; return response('session-a', {saved: true});});
    assert.equal((await ui.http.request('/messages/', {}, 'csrf-value')).saved, true);
    assert.equal(options.headers['X-Chat-Session'], 'session-a');
    assert.equal(options.headers['X-CSRFToken'], 'csrf-value');
});
