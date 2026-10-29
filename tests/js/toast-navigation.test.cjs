const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(require('node:path').join(__dirname, '../..', 'static/js/toast.js'), 'utf8');

function page(storage) {
    const events = {};
    const element = () => ({dataset: {}, classList: {add() {}, remove() {}},
        children: [], append(...nodes) {this.children.push(...nodes);},
        setAttribute() {}, remove() {}, querySelectorAll() {return [];}});
    const region = element();
    const window = {addEventListener(name, callback) {events[name] = callback;},
        requestAnimationFrame(callback) {callback();}, setTimeout() {}};
    const sessionStorage = {getItem: key => storage.get(key) || null,
        setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)};
    vm.runInNewContext(source, {window, sessionStorage, document: {
        getElementById: () => region, createElement: element}, Date});
    return {window, region, events};
}

test('draft feedback appears on destination exactly once, including Back navigation', () => {
    const storage = new Map();
    const detail = page(storage);
    detail.window.YellovedToast.queue({title: 'Offer draft', message: 'Draft saved on this browser.'});
    assert.equal(detail.region.children.length, 0);
    const destination = page(storage);
    assert.equal(destination.region.children.length, 1);
    assert.equal(destination.region.children[0].children[1].children[1].textContent, 'Draft saved on this browser.');
    destination.events.pageshow({persisted: true});
    assert.equal(destination.region.children.length, 1);
    assert.equal(page(storage).region.children.length, 0);

    detail.window.YellovedToast.queue({message: 'Draft discarded.'});
    destination.events.pageshow({persisted: true});
    assert.equal(destination.region.children.length, 2);
    assert.equal(storage.size, 0);
});

test('expired or malformed queued feedback is removed without showing a toast', () => {
    for (const value of ['invalid JSON', JSON.stringify({expires: 0, options: {message: 'Old draft'}})]) {
        const storage = new Map([['yelloved-navigation-toast', value]]);
        assert.equal(page(storage).region.children.length, 0);
        assert.equal(storage.size, 0);
    }
});
