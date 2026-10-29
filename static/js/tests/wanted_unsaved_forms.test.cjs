const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

test('unsaved form changes protect navigation; successful saves reset the baseline', () => {
    const events = {};
    const title = {name: 'title', value: 'Lamp', type: 'text'};
    const revision = {name: 'revision', value: 'v1', type: 'hidden'};
    const modal = {open: true};
    const form = {elements: [title, revision], closest: () => modal};
    const window = {addEventListener: (name, fn) => {events[name] = fn;}};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, '..', 'wanted_unsaved_forms.js'), 'utf8'), {
        window, document: {querySelectorAll: () => [form], addEventListener() {}},
    });
    const api = window.YellovedWantedUnsaved;
    assert.equal(api.dirty(form), false);
    title.value = 'New lamp';
    assert.equal(api.dirty(form), true);
    let blocked = false;
    events.beforeunload({preventDefault() {blocked = true;}});
    assert.equal(blocked, true);
    api.markSaved(form);
    assert.equal(api.dirty(form), false);
    revision.value = 'v2';
    assert.equal(api.dirty(form), false);
});
