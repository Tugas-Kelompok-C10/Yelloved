const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('replacement forms validate images, without binding existing inputs twice', async () => {
    const events = {};
    const makeInput = () => ({id: 'photo', files: [{name: 'huge.png', size: 6 * 1024 * 1024}],
        handlers: [], after() {}, setAttribute() {}, dispatchEvent() {},
        setCustomValidity(message) {this.error = message;},
        addEventListener(name, handler) {if (name === 'change') this.handlers.push(handler);}});
    const first = makeInput();
    let inputs = [first];
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'wanted_image_validation.js'), 'utf8'), {
        document: {querySelectorAll: () => inputs, createElement: () => ({setAttribute() {}})},
        window: {addEventListener: (name, fn) => {events[name] = fn;}}, Event: class {},
    });
    await first.handlers[0]();
    assert.match(first.error, /5 MB/);
    const replacement = makeInput();
    inputs = [first, replacement];
    events['wanted:mounted']();
    events['wanted:mounted']();
    assert.equal(first.handlers.length, 1);
    assert.equal(replacement.handlers.length, 1);
    await replacement.handlers[0]();
    assert.match(replacement.error, /5 MB/);
    replacement.files = [{name: 'script.html', size: 200}];
    await replacement.handlers[0]();
    assert.match(replacement.error, /JPG/);
});
