const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = readFileSync(path.join(__dirname, '..', 'catalogue-search.js'), 'utf8');

function setup(saved = [], query = '') {
    class Element {
        constructor() { this.children = []; this.events = {}; this.value = ''; this.hidden = true; }
        addEventListener(name, handler) { this.events[name] = handler; }
        append(...children) { this.children.push(...children); }
        replaceChildren(...children) { this.children = children; }
        setAttribute(name, value) { this[name] = value; }
        contains(element) { return this === element || this.children.some(child => child.contains?.(element)); }
        focus() { document.activeElement = this; }
    }
    const input = new Element(); input.value = query;
    const results = new Element();
    const clear = new Element();
    const form = new Element(); form.children = [input, results, clear];
    form.querySelector = selector => ({ input, '.nav-search-results': results, '.nav-search-clear': clear }[selector]);
    const documentEvents = {};
    const document = { activeElement: input, querySelector: () => form, createElement: () => new Element(),
        addEventListener(name, handler) { documentEvents[name] = handler; } };
    let stored = JSON.stringify(saved), fetches = 0;
    vm.runInNewContext(source, {
        document,
        localStorage: { getItem: () => stored, setItem: (_, value) => { stored = value; } },
        setTimeout: () => 1, clearTimeout() {},
        fetch: () => { fetches++; },
    });
    return { input, results, clear, form, documentEvents, history: () => JSON.parse(stored), fetches: () => fetches };
}

test('empty focused search shows history, never catalogue requests', () => {
    const app = setup(['lamp', 'book']);
    app.input.events.focus();
    assert.equal(app.results.hidden, false);
    assert.equal(app.results.children[0].children[0].textContent, 'Recent searches');
    assert.equal(app.results.children[1].children[0].children[0].textContent, 'lamp');
    assert.equal(app.fetches(), 0);
});

test('history entries can be removed individually and cleared entirely', () => {
    const app = setup(['lamp', 'book']);
    app.input.events.focus();
    app.results.children[1].children[1].events.click();
    assert.deepEqual(app.history(), ['book']);
    app.results.children[0].children[1].events.click();
    assert.deepEqual(app.history(), []);
    assert.equal(app.results.children[1].textContent, 'No recent searches yet.');
});

test('clearing a query restores history without fetching recent products', () => {
    const app = setup(['book'], 'lamp');
    app.clear.events.click();
    assert.equal(app.input.value, '');
    assert.equal(app.clear.hidden, true);
    assert.equal(app.results.children[0].children[0].textContent, 'Recent searches');
    assert.equal(app.fetches(), 0);
});

test('removing history does not accidentally dismiss the dropdown during bubbling', () => {
    const app = setup(['lamp']);
    app.input.events.focus();
    const button = app.results.children[0].children[1];
    button.events.click();
    assert.equal(app.form.contains(button), false);
    app.documentEvents.click({ target: button, composedPath: () => [button, app.form] });
    assert.equal(app.results.hidden, false);
    assert.deepEqual(app.history(), []);
});
