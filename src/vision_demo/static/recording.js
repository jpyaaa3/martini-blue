/* Record the viewer canvases locally; no extra simulation rendering is needed. */
class ViewerRecording {
  constructor(isSimulationStopped) {
    this.isSimulationStopped = isSimulationStopped;
    this.name = document.getElementById('recording-file');
    this.source = document.getElementById('recording-source');
    this.browseButton = document.getElementById('recording-browse');
    this.startButton = document.getElementById('recording-start');
    this.stopButton = document.getElementById('recording-stop');
    this.status = document.getElementById('recording-status');
    this.download = document.getElementById('recording-download');
    this.fileHandle = null;
    this.session = null;
    this.picking = false;
    this.downloadURL = null;
    this.mimeType = typeof MediaRecorder === 'undefined' ? null : [
      'video/mp4;codecs=avc1', 'video/mp4;codecs=avc1.420028', 'video/mp4',
    ].find(type => MediaRecorder.isTypeSupported(type));
    this.name.value = 'vision-' + new Date().toISOString().replace(/[:.]/g, '-') + '.mp4';
    this.browseButton.addEventListener('click', () => this.browse());
    this.startButton.addEventListener('click', () => { this.start(); this.startButton.blur(); });
    this.stopButton.addEventListener('click', () => { this.stop(); this.stopButton.blur(); });
    this.name.addEventListener('input', () => {
      this.fileHandle = null;
      this.show('Save destination: browser downloads. Use Browse to choose a folder.');
    });
    if (!this.mimeType || !HTMLCanvasElement.prototype.captureStream) {
      this.mimeType = null;
      this.show('This browser cannot record MP4. Open the viewer in a browser with MP4 recording support.', true);
    } else if (!window.showSaveFilePicker) {
      this.show('Folder picker unavailable here. Stop recording downloads the MP4 using the filename above.');
    }
    this.updateButtons();
    addEventListener('beforeunload', event => {
      if (this.session) {
        event.preventDefault();
        event.returnValue = '';
      }
    });
  }

  show(message, error = false) {
    if (this.status.textContent !== message) this.status.textContent = message;
    this.status.classList.toggle('error', error);
  }

  updateButtons() {
    const busy = Boolean(this.session) || this.picking;
    this.name.disabled = busy;
    this.source.disabled = busy;
    this.browseButton.disabled = busy || !window.showSaveFilePicker || !this.mimeType;
    this.startButton.disabled = busy || !this.mimeType || this.isSimulationStopped();
    this.stopButton.disabled = !this.session || this.session.finishing;
  }

  filename() {
    let value = this.name.value.trim();
    if (!value || /[\\/:*?"<>|\x00-\x1f]/.test(value)) {
      throw new Error('Enter a filename, not a path. Use Browse to choose a folder.');
    }
    if (!/\.mp4$/i.test(value)) value += '.mp4';
    this.name.value = value;
    return value;
  }

  async browse() {
    if (this.session || this.picking || !window.showSaveFilePicker) return;
    this.picking = true;
    this.updateButtons();
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: this.filename(),
        id: 'vision-recording',
        types: [{description: 'MP4 video', accept: {'video/mp4': ['.mp4']}}],
        excludeAcceptAllOption: true,
      });
      if (!/\.mp4$/i.test(handle.name)) throw new Error('Choose a filename ending in .mp4.');
      this.fileHandle = handle;
      this.name.value = handle.name;
      this.show('Selected: ' + handle.name + ' · saved to the folder chosen in Browse.');
    } catch (error) {
      if (error.name !== 'AbortError') this.show(error.message, true);
    } finally {
      this.picking = false;
      this.updateButtons();
    }
  }

  start() {
    if (this.session || this.picking || !this.mimeType || this.isSimulationStopped()) return;
    let stream;
    try {
      const filename = this.filename();
      const ids = this.source.value === 'both' ? ['observer', 'mounted'] : [this.source.value];
      const canvases = ids.map(id => document.getElementById(id));
      if (canvases.some(canvas => canvas.dataset.ready !== 'true')) {
        throw new Error('Wait for the selected camera frames before recording.');
      }
      const canvas = document.createElement('canvas');
      canvas.width = Math.ceil(canvases.reduce((sum, c) => sum + c.width, 0) / 2) * 2;
      canvas.height = Math.ceil(Math.max(...canvases.map(c => c.height)) / 2) * 2;
      const context = canvas.getContext('2d', {alpha: false});
      const slots = canvases.map(c => ({width: c.width, height: c.height}));
      const draw = () => {
        context.fillStyle = '#000';
        context.fillRect(0, 0, canvas.width, canvas.height);
        let x = 0;
        canvases.forEach((source, index) => {
          const slot = slots[index];
          const scale = Math.min(slot.width / source.width, canvas.height / source.height);
          const width = source.width * scale;
          const height = source.height * scale;
          context.drawImage(source, x + (slot.width-width)/2, (canvas.height-height)/2, width, height);
          x += slot.width;
        });
      };
      draw();
      stream = canvas.captureStream(30);
      const recorder = new MediaRecorder(stream, {mimeType: this.mimeType, videoBitsPerSecond: 4_000_000});
      const session = {
        recorder, stream, filename, handle: this.fileHandle, chunks: [], bytes: 0,
        finishing: false, error: null, limitReached: false, started: performance.now(),
      };
      session.done = new Promise(resolve => { session.resolve = resolve; });
      recorder.addEventListener('dataavailable', event => {
        if (event.data.size) {
          session.chunks.push(event.data);
          session.bytes += event.data.size;
        }
        // Bound browser memory. The final chunk is still collected by onstop.
        if (session.bytes >= 256 * 1024 * 1024 && !session.finishing) {
          session.limitReached = true;
          this.stop();
        }
      });
      recorder.addEventListener('error', event => {
        session.error = event.error || new Error('MP4 encoding failed.');
        this.stop();
      });
      recorder.addEventListener('stop', () => this.finish(session), {once: true});
      this.session = session;
      recorder.start(1000);
      if (this.downloadURL) URL.revokeObjectURL(this.downloadURL);
      this.downloadURL = null;
      this.download.hidden = true;
      this.download.removeAttribute('href');
      session.timer = setInterval(() => {
        draw();
        const seconds = Math.floor((performance.now()-session.started)/1000);
        const clock = Math.floor(seconds/60) + ':' + String(seconds%60).padStart(2, '0');
        this.show('Recording ● ' + clock + ' · ' + (session.bytes/1048576).toFixed(1) + ' MB');
      }, 1000/30);
      this.show('Recording ● 0:00');
      this.updateButtons();
    } catch (error) {
      if (stream) stream.getTracks().forEach(track => track.stop());
      this.session = null;
      this.show(error.message, true);
      this.updateButtons();
    }
  }

  stop() {
    const session = this.session;
    if (!session) return Promise.resolve();
    if (!session.finishing) {
      session.finishing = true;
      clearInterval(session.timer);
      this.show('Saving MP4…');
      this.updateButtons();
      if (session.recorder.state !== 'inactive') session.recorder.stop();
      // An encoder error also queues a stop event; let it flush its last chunk.
    }
    return session.done;
  }

  async finish(session) {
    session.finishing = true;
    clearInterval(session.timer);
    session.stream.getTracks().forEach(track => track.stop());
    this.updateButtons();
    let writable;
    try {
      if (session.error) throw session.error;
      const blob = new Blob(session.chunks, {type: session.recorder.mimeType});
      if (!blob.size) throw new Error('No video frames were recorded. Please try again.');
      // Keep a recovery download available if the chosen file cannot be written.
      if (this.downloadURL) URL.revokeObjectURL(this.downloadURL);
      this.downloadURL = URL.createObjectURL(blob);
      this.download.href = this.downloadURL;
      this.download.download = session.filename;
      this.download.hidden = false;
      this.download.textContent = 'Download ' + session.filename;
      if (session.handle) {
        writable = await session.handle.createWritable();
        await writable.write(blob);
        await writable.close();
        writable = null;
        this.show('Saved: ' + session.filename + (session.limitReached ? ' · stopped at 256 MB buffer limit.' : ''));
      } else {
        this.download.click();
        this.show('MP4 download ready: ' + session.filename + (session.limitReached ? ' · stopped at 256 MB buffer limit.' : ''));
      }
    } catch (error) {
      if (writable) await writable.abort().catch(() => {});
      this.show('Could not save recording: ' + error.message +
        (this.downloadURL && !session.error ? ' Use the Download link to save this recording.' : ''), true);
    } finally {
      session.chunks.length = 0;
      // Choose a destination again for each recording to avoid overwriting the last one.
      this.fileHandle = null;
      this.session = null;
      this.updateButtons();
      session.resolve();
    }
  }
}
