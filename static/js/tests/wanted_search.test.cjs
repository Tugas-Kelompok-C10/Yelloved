const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '..', 'wanted_board.js'), 'utf8');

function element() {
    const handlers = new Map();
    return {dataset: {}, value: '', isConnected: true, classList: {toggle() {}},
        setAttribute(name, value) {this[name] = value;},
        addEventListener(name, fn, {signal} = {}) {
            const list = handlers.get(name) || []; list.push(fn); handlers.set(name, list);
            signal?.addEventListener('abort', () => handlers.set(name, list.filter(item => item !== fn)));
        },
        emit(name, detail = {}) {
            const event = {detail, target: {closest: () => detail.link}, defaultPrevented: false, preventDefault() {this.defaultPrevented = true;}};
            for (const fn of handlers.get(name) || []) fn(event);
            return event;
        }};
}
function harness() {
    const form = element(), input = element(), category = element(), sort = element(), button = element(), page = element();
    page.value = '1';
    const grid = element(), results = element(), state = element(), status = element(), doc = element();
    const chips = ['', 'books'].map(value => Object.assign(element(), {dataset: {categoryChip: value}}));
    let submissions = 0;
    form.requestSubmit = () => {submissions++;};
    form.querySelector = selector => ({'[name=q]': input, '[name=category]': category, '[name=sort]': sort, '[name=page]': page,
        '[data-wanted-sort]': button, '[data-wanted-sort-status]': status})[selector];
    form.querySelectorAll = () => chips;
    results.querySelector = selector => selector === '.wanted-grid' ? grid : state;
    doc.querySelector = () => form; doc.getElementById = () => results;
    const urls = [], notifications = [], scrolls = [], processed = [];
    const window = {htmx: {process: node => processed.push(node)}, history: {state: {}, replaceState: (_, __, url) => urls.push(url)},
        scrollTo: options => scrolls.push(options), YellovedToast: {show: options => notifications.push(options)}};
    vm.runInNewContext(script, {window, document: doc, AbortController});
    const xhr = {aborted: false, abort() {this.aborted = true;}};
    const request = (paginate = false) => {
        if (paginate) results.emit('click', {link: {dataset: {wantedPage: '2'}}});
        doc.emit('htmx:beforeRequest', {target: results, xhr});
    };
    const swap = (values = {}) => {
        state.dataset = {category: '', sort: '', page: '1', url: '/wanted-post/', ...values};
        doc.emit('htmx:afterSwap', {target: results, xhr});
        doc.emit('htmx:afterRequest', {target: results, xhr, failed: false});
    };
    return {form, input, category, sort, page, button, chips, doc, results, xhr, window, urls, notifications, scrolls, processed,
        submissions: () => submissions, request, swap};
}

test('category and sorting submit one shared form and keep both values', () => {
    const ui = harness();
    ui.button.emit('click');
    ui.chips[1].emit('click');
    assert.equal(ui.sort.value, 'budget_asc');
    assert.equal(ui.category.value, 'books');
    ui.button.emit('click');
    assert.equal(ui.sort.value, 'budget_desc');
    assert.equal(ui.submissions(), 3);
});

test('input cancels an old request immediately and prevents its late swap', () => {
    const ui = harness(); ui.request(); ui.input.emit('input');
    assert.equal(ui.xhr.aborted, true);
    assert.equal(ui.doc.emit('htmx:beforeSwap', {target: ui.results, xhr: ui.xhr}).defaultPrevented, true);
    assert.equal(ui.urls.length, 0);
});

test('failed sort keeps the confirmed filters and URL and shows a retry toast', () => {
    const ui = harness(); ui.button.emit('click'); ui.request();
    ui.doc.emit('htmx:afterRequest', {target: ui.results, xhr: ui.xhr, failed: true});
    assert.equal(ui.sort.value, '');
    assert.equal(ui.urls.length, 0);
    assert.match(ui.notifications[0].message, /press Enter/);
});

test('successful pagination confirms filters and scrolls to top', () => {
    const ui = harness(); ui.request(true);
    ui.swap({category: 'books', sort: 'budget_asc', page: '2', url: '/wanted-post/?category=books&sort=budget_asc&page=2'});
    assert.equal(ui.category.value, 'books');
    assert.equal(ui.sort.value, 'budget_asc');
    assert.match(ui.urls[0], /page=2/);
    assert.equal(ui.scrolls[0].top, 0);
    assert.equal(ui.page.value, '2');
    ui.input.emit('input');
    assert.equal(ui.page.value, '1');
});

test('removing the board aborts its request and detaches its event listeners', () => {
    const ui = harness(); ui.request(); ui.window.YellovedWantedBoard.destroy();
    assert.equal(ui.xhr.aborted, true);
    ui.swap({url: '/stale/'});
    assert.equal(ui.urls.length, 0);
});

test('HTMX request parameters trim and cap the query at 70 characters', () => {
    const ui = harness(); ui.input.value = '  ' + 'x'.repeat(80);
    const parameters = {};
    ui.doc.emit('htmx:configRequest', {target: ui.results, parameters});
    assert.equal(parameters.q, 'x'.repeat(70));
    assert.equal(ui.processed.length, 2);
});
