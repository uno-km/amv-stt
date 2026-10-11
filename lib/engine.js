/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * termux-stt - Engine Abstraction for Node.js
 */

class TranscriptResult {
  constructor(text, segments = [], language = 'ko', duration = 0) {
    this.text = text;
    this.segments = segments;
    this.language = language;
    this.duration = duration;
  }

  toJson() {
    return JSON.stringify(this, null, 2);
  }

  toSrt() {
    return this.segments.map((seg, i) => {
      const start = formatTime(seg.start);
      const end = formatTime(seg.end);
      return `${i + 1}\n${start} --> ${end}\n${seg.text}\n`;
    }).join('\n');
  }

  toVtt() {
    const body = this.segments.map((seg) => {
      const start = formatTime(seg.start, true);
      const end = formatTime(seg.end, true);
      return `${start} --> ${end}\n${seg.text}\n`;
    }).join('\n');
    return `WEBVTT\n\n${body}`;
  }

  toRttm(fileId = 'audio') {
    return this.segments.map((seg) => {
      const spk = seg.speaker || 'Speaker_0';
      const dur = (seg.end - seg.start).toFixed(2);
      return `SPEAKER ${fileId} 1 ${seg.start.toFixed(2)} ${dur} <NA> <NA> ${spk} <NA> <NA>`;
    }).join('\n');
  }
}

class Segment {
  constructor(start, end, text, speaker = null, confidence = null) {
    this.start = start;
    this.end = end;
    this.text = text;
    this.speaker = speaker;
    this.confidence = confidence;
  }
}

function formatTime(seconds, isVtt = false) {
  const s = Math.max(0, seconds || 0);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = Math.floor(s % 60);
  const ms = Math.floor((s % 1) * 1000);

  const pad = (n, z = 2) => String(n).padStart(z, '0');
  const sep = isVtt ? '.' : ',';
  return `${pad(hrs)}:${pad(mins)}:${pad(secs)}${sep}${pad(ms, 3)}`;
}

class Engine {
  constructor(config = {}) {
    this.config = config;
  }

  async transcribe(audioPath, options = {}) {
    throw new Error('transcribe() must be implemented by subclass');
  }

  async diarize(audioPath, numSpeakers = 2) {
    throw new Error('diarize() must be implemented by subclass');
  }

  streamMic(duration = null) {
    throw new Error('streamMic() must be implemented by subclass');
  }

  getInfo() {
    return { name: this.constructor.name, config: this.config };
  }
}

module.exports = {
  Engine,
  TranscriptResult,
  Segment,
  formatTime
};
