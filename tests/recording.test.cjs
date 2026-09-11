// Browser-independent lifecycle checks; real MP4 encoding is covered by Playwright.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function setup({supported = true, picker} = {}) {
  const records = [], downloads = [], revoked = [], tracks = [], elements = new Map();
  class Element {
    constructor(id) {
      this.id = id;
      this.value = id === 'recording-source' ? 'both' : '';
      this.dataset = {ready: 'true'};
      this.width = 960;
      this.height = 540;
      this.hidden = true;
      this.textContent = '';
      this.events = {};
      this.classList = {toggle() {}};
    }
    addEventListener(type, callback) { (this.events[type] ||= []).push(callback); }
    emit(type, event = {}) { for (const callback of this.events[type] || []) callback(event); }
    click() { if (this.id === 'recording-download') downloads.push(this.download); this.emit('click'); }
    blur() {}
    removeAttribute(name) { delete this[name]; }
  }
  class Canvas extends Element {
    getContext() { return {fillRect() {}, drawImage() {}}; }
    captureStream() {
      const track = {stopped: false, stop() { this.stopped = true; }};
      tracks.push(track);
      return {canvas: this, getTracks: () => [track]};
    }
  }
  class Recorder extends Element {
    static isTypeSupported() { return supported; }
    constructor(stream, options) {
      super(); this.stream = stream; this.mimeType = options.mimeType; this.state = 'inactive'; records.push(this);
    }
    start() { this.state = 'recording'; }
    stop() {
      this.state = 'inactive';
      queueMicrotask(() => {
        this.emit('dataavailable', {data: new Blob(['final-frame'], {type: this.mimeType})});
        this.emit('stop');
      });
    }
  }
  const blobs = [];
  const context = vm.createContext({
    MediaRecorder: Recorder, HTMLCanvasElement: Canvas, Blob, Date, Promise, Error,
    performance: {now: () => 0}, setInterval: () => 1, clearInterval() {}, addEventListener() {},
    URL: {createObjectURL(blob) { blobs.push(blob); return 'blob:' + blobs.length; }, revokeObjectURL(url) { revoked.push(url); }},
    document: {
      getElementById(id) {
        if (!elements.has(id)) elements.set(id, new Canvas(id));
        return elements.get(id);
      },
      createElement: () => new Canvas('composite'),
    },
    showSaveFilePicker: picker,
  });
  context.window = context;
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../src/vision_demo/static/recording.js'), 'utf8'), context);
  vm.runInContext('globalThis.recording = new ViewerRecording(() => false)', context);
  return {ui: context.recording, records, downloads, revoked, tracks, elements, blobs, context};
}

test('start/stop waits for final chunk, downloads once, and releases capture tracks', async () => {
  const {ui, records, downloads, tracks, blobs} = setup();
  ui.name.value = 'drive';
  ui.start();
  ui.start();
  assert.equal(records.length, 1);
  assert.equal(records[0].stream.canvas.width, 1920);
  assert.equal(ui.name.disabled, true);
  const stopped = ui.stop();
  assert.equal(ui.stop(), stopped);
  await stopped;
  assert.deepEqual(downloads, ['drive.mp4']);
  assert.equal(await blobs[0].text(), 'final-frame');
  assert.equal(tracks[0].stopped, true);
  assert.equal(ui.startButton.disabled, false);
  assert.equal(ui.stopButton.disabled, true);
});

test('Browse writes and closes selected file after stop, and changing filename clears destination', async () => {
  const writes = [];
  let closed = false;
  const handle = {name: 'chosen.mp4', createWritable: async () => ({
    write: async blob => writes.push(await blob.text()), close: async () => { closed = true; },
  })};
  const {ui, downloads} = setup({picker: async () => handle});
  await ui.browse();
  assert.equal(ui.name.value, 'chosen.mp4');
  ui.start();
  await ui.stop();
  assert.deepEqual(writes, ['final-frame']);
  assert.equal(closed, true);
  assert.equal(downloads.length, 0);
  assert.equal(ui.fileHandle, null);
  await ui.browse();
  ui.name.value = 'other.mp4';
  ui.name.emit('input');
  assert.equal(ui.fileHandle, null);
});

test('failed file write preserves a recovery download and aborts uncommitted file', async () => {
  let aborted = false;
  const {ui, blobs} = setup({picker: async () => ({name: 'full.mp4', createWritable: async () => ({
    write: async () => { throw new Error('Disk full'); }, abort: async () => { aborted = true; },
  })})});
  await ui.browse();
  ui.start();
  await ui.stop();
  assert.equal(aborted, true);
  assert.match(ui.status.textContent, /Disk full/);
  assert.equal(ui.download.hidden, false);
  assert.equal(await blobs[0].text(), 'final-frame');
  assert.equal(ui.startButton.disabled, false);
});

test('cancelled picker does not change destination or leave controls locked', async () => {
  const {ui} = setup({picker: async () => { const e = new Error('cancel'); e.name = 'AbortError'; throw e; }});
  const name = ui.name.value;
  await ui.browse();
  assert.equal(ui.name.value, name);
  assert.equal(ui.startButton.disabled, false);
});

test('unsupported MP4, invalid filenames and missing frames never start a recorder', () => {
  const unsupported = setup({supported: false});
  unsupported.ui.start();
  assert.equal(unsupported.records.length, 0);
  assert.match(unsupported.ui.status.textContent, /cannot record MP4/);
  const {ui, records, context} = setup();
  ui.name.value = '/some/path.mp4';
  ui.start();
  assert.match(ui.status.textContent, /Use Browse/);
  ui.name.value = 'valid.mp4';
  context.document.getElementById('mounted').dataset.ready = 'false';
  ui.start();
  assert.equal(records.length, 0);
  assert.match(ui.status.textContent, /Wait for/);
});

test('encoder error cleans up and re-enables controls without downloading corrupt data', async () => {
  const {ui, records, tracks, downloads} = setup();
  ui.start();
  const finished = ui.session.done;
  records[0].emit('error', {error: new Error('Encoder unavailable')});
  await finished;
  assert.match(ui.status.textContent, /Encoder unavailable/);
  assert.equal(tracks[0].stopped, true);
  assert.equal(downloads.length, 0);
  assert.equal(ui.startButton.disabled, false);
});
