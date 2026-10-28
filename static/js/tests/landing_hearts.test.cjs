const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'landing.js'), 'utf8');

test('rapid hearts send one request without queueing, then recover after failure', async () => {
    let submit, finish;
    let calls = 0;
    const toasts = [];
    const count = {textContent: ''}, feedback = {textContent: ''};
    const button = {setAttribute() {}, removeAttribute() {}, getBoundingClientRect: () => ({left: 0, top: 0, width: 10, height: 10})};
    const form = {action: '/love/', addEventListener: (_, handler) => { submit = handler; }};
    const template = {content: {firstElementChild: {cloneNode: () => ({style: {}, remove() {}})}}};
    const hero = {
        querySelector: selector => ({'[data-love-form]': form, '[data-heart-count]': count,
            '[data-love-message]': feedback, '[data-love-burst]': template, '.landing-love-logo': button})[selector],
        getBoundingClientRect: () => ({left: 0, top: 0}), append() {},
    };
    vm.runInNewContext(source, {document: {querySelector: () => hero}, Date, AbortSignal,
        FormData: class {}, window: {setTimeout() {}, YellovedToast: {show: toast => toasts.push(toast)}},
        fetch: () => { calls++; return new Promise(resolve => { finish = resolve; }); }});
    const click = () => submit({preventDefault() {}, submitter: button});
    for (let i = 0; i < 30; i++) click();
    assert.equal(calls, 1);
    finish({ok: false});
    await new Promise(setImmediate);
    assert.equal(toasts[0].type, 'error');
    assert.equal(calls, 1);
    click();
    assert.equal(calls, 2);
    finish({ok: true, json: async () => ({count: 1})});
    await new Promise(setImmediate);
    assert.equal(count.textContent, '1 hearts shared in this visit.');
    assert.equal(calls, 2);
});
