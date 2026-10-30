const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '..', 'chat_session.js'), 'utf8');

function transport(fetch) {
    const events = [], timers = new Map(), handlers = {};
    let timerId = 0;
    const window = {dispatchEvent: event => events.push(event), addEventListener: (name, fn) => {handlers[name] = fn;}};
    vm.runInNewContext(script, {window, AbortController, fetch,
        setTimeout: (fn, ms) => {timers.set(++timerId, {fn, ms}); return timerId;}, clearTimeout: id => timers.delete(id),
        CustomEvent: class {constructor(type, options) {this.type = type; this.detail = options.detail;}},
        document: {querySelector: () => ({dataset: {chatSession: 'session-a', chatUser: '1'}})}});
    return {http: window.YellovedChatHTTP, events, timers, handlers};
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
    assert.equal(ui.timers.size, 0);
});

test('a stalled send times out, aborts its connection, and allows an idempotent retry', async () => {
    let signal, calls = 0;
    const ui = transport(async (_, options) => {
        signal = options.signal;
        if (++calls > 1) return response('session-a', {saved: true});
        return new Promise(() => {});
    });
    const pending = ui.http.request('/messages/', {client_id: 'same-token'}, 'csrf');
    const timer = [...ui.timers.values()][0]; assert.equal(timer.ms, 15000); timer.fn();
    await assert.rejects(pending, /timed out.*Retry/);
    assert.equal(signal.aborted, true);
    assert.equal(ui.http.blocked, false);
    assert.equal(ui.timers.size, 0);
    assert.equal((await ui.http.request('/messages/', {client_id: 'same-token'}, 'csrf')).saved, true);
    assert.equal(ui.events.length, 0);
});

test('timeout also covers a stalled response body', async () => {
    const ui = transport(async () => ({...response('session-a'), json: () => new Promise(() => {})}));
    const pending = ui.http.request('/inbox/');
    await Promise.resolve();
    [...ui.timers.values()][0].fn();
    await assert.rejects(pending, /too long/);
    assert.equal(ui.timers.size, 0);
});

test('leaving the page aborts outstanding connections', async () => {
    let signal;
    const ui = transport(async (_, options) => {
        signal = options.signal;
        return new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('Cancelled'))));
    });
    const pending = ui.http.request('/inbox/');
    ui.handlers.pagehide();
    await assert.rejects(pending, /Cancelled/);
    assert.equal(signal.aborted, true);
    assert.equal(ui.http.blocked, false);
    assert.equal(ui.timers.size, 0);
});
