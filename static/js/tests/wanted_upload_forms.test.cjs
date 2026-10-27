const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const script = fs.readFileSync(path.join(__dirname, "..", "wanted_upload_forms.js"), "utf8");

function harness(fetch) {
    const listeners = {};
    const selectedPhoto = { name: "photo.png" };
    const errors = [];
    const input = { files: [selectedPhoto], setAttribute() {}, focus() {} };
    const field = {
        dataset: { uploadField: "budget" },
        querySelector: () => input,
        append: (error) => errors.push(error),
    };
    const submit = { textContent: "Save", disabled: false };
    const cancel = { disabled: false };
    const modal = { dataset: {}, addEventListener() {}, querySelectorAll: () => [submit, cancel] };
    const summary = { append: (error) => errors.push(error) };
    const form = {
        action: "/wanted-post/create/",
        token: "same-create-token",
        selectedPhoto,
        closest: () => modal,
        querySelector: (selector) => selector === "[data-upload-form-errors]" ? summary : submit,
        querySelectorAll: (selector) => selector === "[data-upload-field]" ? [field] : errors,
        addEventListener: (name, callback) => { listeners[name] = callback; },
        setAttribute() {},
        reportValidity: () => true,
        reset: () => assert.fail("Validation must not reset the form"),
    };
    const redirects = [];
    vm.runInNewContext(script, {
        document: {
            querySelectorAll: () => [form],
            createElement: () => ({ dataset: {}, remove() {} }),
        },
        FormData: class {
            constructor(element) {
                this.token = element.token;
                this.photo = element.selectedPhoto;
            }
        },
        window: { location: { assign: (url) => redirects.push(url) } },
        fetch,
    });
    return { submit: () => listeners.submit({ preventDefault() {} }),
        errors, input, selectedPhoto, form, submitButton: submit, cancel, redirects };
}

function response(status, data) {
    return { status, ok: status < 400, headers: { get: () => "application/json" },
        json: async () => data };
}

test("double click sends one request; validation errors retain photo and token for retry", async () => {
    let finish;
    const requests = [];
    const ui = harness((url, options) => {
        requests.push(options);
        return new Promise((resolve) => { finish = resolve; });
    });
    const first = ui.submit();
    assert.equal(ui.submitButton.disabled, true);
    assert.equal(ui.submitButton.textContent, "Saving…");
    await ui.submit();
    assert.equal(requests.length, 1);
    finish(response(422, { errors: { budget: [{ message: "Invalid budget" }] } }));
    await first;
    assert.equal(ui.input.files[0], ui.selectedPhoto);
    assert.equal(ui.errors[0].textContent, "Invalid budget");
    assert.equal(ui.submitButton.disabled, false);
    assert.equal(ui.cancel.disabled, false);
    const retry = ui.submit();
    assert.equal(requests[1].body.token, requests[0].body.token);
    assert.equal(requests[1].body.photo, ui.selectedPhoto);
    finish(response(200, { redirect_url: "/wanted-post/1/" }));
    await retry;
    assert.equal(ui.redirects[0], "/wanted-post/1/");
});

test("network failure preserves input and enables retry", async () => {
    const ui = harness(async () => { throw new Error("Connection lost"); });
    await ui.submit();
    assert.equal(ui.input.files[0], ui.selectedPhoto);
    assert.equal(ui.submitButton.disabled, false);
    assert.equal(ui.errors[0].textContent, "Connection lost");
    assert.equal(ui.redirects.length, 0);
});

test("expired login response preserves the selected file", async () => {
    const ui = harness(async () => ({ redirected: true }));
    await ui.submit();
    assert.equal(ui.input.files[0], ui.selectedPhoto);
    assert.match(ui.errors[0].textContent, /session may have expired/);
    assert.equal(ui.redirects.length, 0);
});
