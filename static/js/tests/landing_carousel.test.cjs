const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '..', 'landing-items.js'), 'utf8');

function harness() {
    const listeners = {};
    const timers = new Map();
    const classes = new Set();
    let timerId = 0;
    let left = 0;
    const calls = [];
    const previous = {addEventListener(name, handler) { this[name] = handler; }};
    const next = {addEventListener(name, handler) { this[name] = handler; }};
    const controls = {querySelector: selector => selector.includes('prev') ? previous : next};
    const status = {textContent: ''};
    const fire = (name, data = {}) => listeners[name]?.({preventDefault() {}, stopPropagation() {}, ...data});
    const cards = Array.from({length: 8}, (_, i) => ({offsetLeft: i * 100}));
    const track = {
        clientWidth: 400, scrollWidth: 800,
        get scrollLeft() { return left; },
        set scrollLeft(value) { const old = left; left = Math.max(0, Math.min(400, value)); if (old !== left) fire('scroll'); },
        querySelectorAll: () => cards,
        addEventListener: (name, handler) => { listeners[name] = handler; },
        scrollTo(options) { calls.push(options.left); this.scrollLeft = options.left; },
        setPointerCapture() {}, hasPointerCapture: () => false, releasePointerCapture() {},
        classList: {add: value => classes.add(value), remove: value => classes.delete(value),
            toggle(value, enabled) { if (enabled) classes.add(value); else classes.delete(value); }},
    };
    const section = {querySelector: selector => selector.includes('grid') ? track : selector.includes('controls') ? controls : status};
    vm.runInNewContext(source, {
        document: {querySelector: () => section},
        window: {matchMedia: () => ({matches: false}),
            setTimeout(handler) { const id = ++timerId; timers.set(id, handler); return id; },
            clearTimeout: id => timers.delete(id)},
        getComputedStyle: () => ({paddingLeft: '0', getPropertyValue: () => '4'}),
        ResizeObserver: class { constructor(callback) { this.callback = callback; } observe() { this.callback(); } },
    });
    calls.length = 0;
    const flush = () => {
        let rounds = 0;
        while (timers.size) {
            assert.ok(++rounds < 20, 'The carousel must settle instead of scrolling forever');
            const batch = [...timers.entries()];
            timers.clear();
            batch.forEach(([, callback]) => callback());
        }
    };
    return {track, previous, next, calls, classes, fire, flush};
}

test('buttons move four cards and stop animating at the final page', () => {
    const ui = harness();
    ui.next.click(); ui.flush();
    assert.equal(ui.track.scrollLeft, 400);
    assert.equal(ui.next.disabled, true);
    assert.equal(ui.classes.has('is-sliding'), false);
    assert.deepEqual(ui.calls, [400]);
    ui.previous.click(); ui.flush();
    assert.equal(ui.track.scrollLeft, 0);
    assert.equal(ui.previous.disabled, true);
});

test('a mouse drag snaps to a whole page, never a single card', () => {
    const ui = harness();
    ui.fire('pointerdown', {pointerType: 'mouse', button: 0, pointerId: 1, clientX: 300, clientY: 100});
    ui.fire('pointermove', {pointerId: 1, clientX: 200, clientY: 100});
    ui.fire('pointerup'); ui.flush();
    assert.equal(ui.track.scrollLeft, 400);
    assert.equal(ui.classes.has('is-sliding'), false);
});

test('a short touch swipe advances to the next group of four', () => {
    const ui = harness();
    ui.fire('touchstart', {touches: [{clientX: 300, clientY: 100}]});
    ui.fire('touchend', {changedTouches: [{clientX: 240, clientY: 100}]});
    ui.flush();
    assert.equal(ui.track.scrollLeft, 400);
});

test('trackpad momentum triggers one page change and settles', () => {
    const ui = harness();
    for (let i = 0; i < 6; i++) ui.fire('wheel', {deltaX: 40, deltaY: 0});
    ui.flush();
    assert.deepEqual(ui.calls, [400]);
    assert.equal(ui.classes.has('is-sliding'), false);
});
