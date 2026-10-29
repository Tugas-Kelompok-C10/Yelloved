const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '..', 'wanted_board.js'), 'utf8');

function harness(fetch) {
    const handlers = {}, urls = [], notifications = [];
    const form = {dataset: {}, action: 'https://local.test/wanted-post/', addEventListener: (name, fn) => {handlers[name] = fn;}};
    const grid = {innerHTML: 'Current cards', classList: {add() {}, remove() {}}, setAttribute() {}};
    const input = {value: 'lamp', dataset: {}, addEventListener() {}};
    const chips = ['', 'books'].map(category => ({dataset: {categoryChip: category}, classList: {contains: () => !category, toggle() {}}, setAttribute() {}, addEventListener(name, fn) {this.click = fn;}}));
    const sort = {dataset: {sort: ''}, setAttribute(name, value) {this[name] = value;}, addEventListener(name, fn) {this.click = fn;}};
    const pagination = {innerHTML: '', addEventListener() {}};
    const window = {location: {origin: 'https://local.test', assign: url => urls.push(String(url))},
        history: {replaceState: (_, __, url) => urls.push(String(url))}, clearTimeout, setTimeout,
        YellovedToast: {show: value => notifications.push(value)}};
    vm.runInNewContext(script, {window, URL, AbortController, fetch,
        document: {querySelector: selector => ({'[data-ajax-search]': form, '.wanted-grid': grid, '[data-wanted-pagination]': pagination, '[data-wanted-sort]': sort})[selector] || null,
            querySelectorAll: () => chips, getElementById: () => input}});
    return {window, grid, urls, notifications, sort, chips, submit: () => handlers.submit({preventDefault() {}})};
}

test('a response from a removed board cannot change cards or URL', async () => {
    let finish, signal;
    const ui = harness((_, options) => {signal = options.signal; return new Promise(resolve => {finish = resolve;});});
    ui.submit();
    ui.window.YellovedWantedBoard.destroy();
    assert.equal(signal.aborted, true);
    finish({ok: true, json: async () => ({html: 'Stale cards', pagination_html: '', selected_category: '', page_number: 1})});
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.grid.innerHTML, 'Current cards');
    assert.equal(ui.urls.length, 0);
});

test('failed search retains results and URL, shows a toast, and permits retry', async () => {
    let attempts = 0;
    const ui = harness(async () => {
        if (++attempts === 1) throw new Error('Offline');
        return {ok: true, json: async () => ({html: 'New cards', pagination_html: '', selected_category: '', page_number: 1})};
    });
    ui.submit();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.grid.innerHTML, 'Current cards');
    assert.equal(ui.urls.length, 0);
    assert.equal(ui.notifications[0].type, 'error');
    assert.match(ui.notifications[0].message, /press Enter/);
    ui.submit();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.grid.innerHTML, 'New cards');
    assert.equal(ui.urls.length, 1);
});

test('sort toggles asc/desc and remains selected when clicking category chips', async () => {
    const requested = [];
    const ui = harness(async url => {
        requested.push(String(url));
        return {ok: true, json: async () => ({html: 'Sorted', pagination_html: '', selected_category: url.searchParams.get('category') || '',
            selected_sort: url.searchParams.get('sort') || '', page_number: 1})};
    });
    ui.sort.click(); await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.sort.dataset.sort, 'budget_asc');
    ui.chips[1].click(); await new Promise(resolve => setImmediate(resolve));
    assert.match(requested[1], /category=books/);
    assert.match(requested[1], /sort=budget_asc/);
    ui.sort.click(); await new Promise(resolve => setImmediate(resolve));
    assert.match(requested[2], /category=books/);
    assert.match(requested[2], /sort=budget_desc/);
    assert.match(requested[2], /q=lamp/);
    assert.equal(ui.sort.dataset.sort, 'budget_desc');
});

test('failed sort restores the confirmed direction without changing cards or URL', async () => {
    const ui = harness(async () => {throw new Error('Offline');});
    ui.sort.click(); await new Promise(resolve => setImmediate(resolve));
    assert.equal(ui.sort.dataset.sort, '');
    assert.equal(ui.grid.innerHTML, 'Current cards');
    assert.equal(ui.urls.length, 0);
    assert.equal(ui.notifications[0].type, 'error');
});
