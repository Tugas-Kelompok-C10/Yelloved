const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '..', 'wanted_upload_forms.js'), 'utf8');

function harness(fetch, deletion = false) {
    const listeners = {}, errors = [], notifications = [];
    const input = {value: 'Study lamp', setAttribute() {}, focus() {}};
    const field = {dataset: {uploadField: 'budget'}, querySelector: () => input, append: node => errors.push(node)};
    const submit = {textContent: deletion ? 'Delete' : 'Save', disabled: false};
    const cancel = {disabled: false};
    const modal = {dataset: {}, open: true, querySelectorAll: () => [submit, cancel],
        close() {this.open = false;}, showModal() {this.open = true;}, remove() {}};
    const card = {hidden: false, innerHTML: 'Old lamp'};
    let status;
    const main = {querySelector: selector => selector === '.wanted-detail-card' ? card : status,
        setAttribute() {}, removeAttribute() {}, after() {}, append(node) {status = node;}};
    const form = {
        action: '/wanted-post/uuid/' + (deletion ? 'delete/' : 'edit/'),
        dataset: {boardUrl: '/wanted-post/', detailUrl: '/wanted-post/uuid/'},
        elements: {revision: {value: 'original'}}, isConnected: true,
        matches: selector => selector.includes('data-ajax-upload') || (deletion && selector.includes('data-ajax-delete')),
        closest: () => modal, reportValidity: () => true,
        querySelector: selector => selector === '[data-upload-form-errors]' ? {append: node => errors.push(node)} : submit,
        querySelectorAll: selector => selector === '[data-upload-field]' ? [field] : [],
        setAttribute() {}, removeAttribute() {},
    };
    const location = {href: 'https://local.test/wanted-post/uuid/'};
    const window = {YellovedToast: {show: value => notifications.push(value)}, dispatchEvent() {}, scrollTo() {}};
    const doc = {title: 'Lamp',
        addEventListener: (name, callback) => {listeners[name] = callback;},
        querySelectorAll: selector => selector === 'dialog[data-auto-open=true]' ? [] : [modal],
        querySelector: selector => selector === '[data-ajax-delete]' ? null : selector === '.wanted-detail-card' ? card : selector === '[data-delete-title]' ? {} : main,
        createElement: () => ({dataset: {}, setAttribute() {}, remove() {status = undefined;}}),
    };
    vm.runInNewContext(script, {document: doc, window, location, fetch, FormData: class {constructor() {this.title = input.value;}},
        history: {state: null, replaceState() {}}, Event: class {}});
    return {submit: () => listeners.submit({target: form, preventDefault() {}}), form, input, errors,
        submitButton: submit, cancel, modal, card, notifications};
}
const response = (status, data) => ({status, ok: status < 400, headers: {get: () => 'application/json'}, json: async () => data});

test('access errors show actionable feedback and keep entered values', async () => {
    for (const result of [response(404, {message: 'Post unavailable or permission denied.'}),
        {status: 403, ok: false, headers: {get: () => 'text/html'}}]) {
        const ui = harness(async () => result);
        await ui.submit();
        assert.match(ui.errors[0].textContent, /permission|security token/);
        assert.equal(ui.notifications[0].type, 'error');
        assert.equal(ui.input.value, 'Study lamp');
        assert.equal(ui.submitButton.disabled, false);
    }
});

test('double submit sends one request; validation preserves input and permits retry', async () => {
    let finish;
    const requests = [];
    const ui = harness((url, options) => {requests.push(options); return new Promise(resolve => {finish = resolve;});});
    const first = ui.submit();
    await ui.submit();
    assert.equal(requests.length, 1);
    assert.equal(ui.submitButton.disabled, true);
    finish(response(422, {errors: {budget: [{message: 'Invalid budget'}]}}));
    await first;
    assert.equal(ui.input.value, 'Study lamp');
    assert.equal(ui.errors[0].textContent, 'Invalid budget');
    assert.equal(ui.submitButton.disabled, false);
    const retry = ui.submit();
    finish(response(200, {detail_html: 'Updated lamp', title: 'Lamp', revision: 'new', message: 'Saved'}));
    await retry;
    assert.equal(ui.card.innerHTML, 'Updated lamp');
    assert.equal(ui.form.elements.revision.value, 'new');
    assert.equal(ui.modal.open, false);
});
test('network failure keeps the form usable', async () => {
    const ui = harness(async () => {throw new Error('Connection lost');});
    await ui.submit();
    assert.equal(ui.input.value, 'Study lamp');
    assert.equal(ui.submitButton.disabled, false);
    assert.equal(ui.errors[0].textContent, 'Connection lost');
});
test('expired login preserves entered details', async () => {
    const ui = harness(async () => ({redirected: true}));
    await ui.submit();
    assert.match(ui.errors[0].textContent, /session may have expired/);
    assert.equal(ui.input.value, 'Study lamp');
});
test('optimistic deletion hides the post before response and rolls back on failure', async () => {
    let fail;
    const ui = harness(() => new Promise((_, reject) => {fail = reject;}), true);
    const request = ui.submit();
    assert.equal(ui.card.hidden, true);
    assert.equal(ui.modal.open, false);
    await ui.submit(); // Still pending: no second request.
    fail(new Error('Offline'));
    await request;
    assert.equal(ui.card.hidden, false);
    assert.equal(ui.modal.open, true);
    assert.equal(ui.submitButton.disabled, false);
    assert.match(ui.errors[0].textContent, /Offline/);
});
test('confirmed deletion is not rolled back when refreshing the board fails', async () => {
    let calls = 0;
    const ui = harness(async () => {
        if (++calls === 1) return response(200, {board_url: '/wanted-post/', message: 'Deleted'});
        throw new Error('Board refresh failed');
    }, true);
    await ui.submit();
    assert.equal(ui.card.hidden, true);
    assert.equal(ui.modal.open, false);
    assert.match(ui.notifications[0].message, /was deleted/);
});
