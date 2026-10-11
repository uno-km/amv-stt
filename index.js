/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * termux-stt Node.js entry point (v2.0.0)
 */

const { Engine, TranscriptResult, Segment, formatTime } = require('./lib/engine');
const { WhisperEngine } = require('./lib/whisper');
const { SherpaEngine } = require('./lib/sherpa');
const { HybridEngine } = require('./lib/hybrid');

function createEngine(engineName = 'whisper', options = {}) {
  const name = String(engineName).toLowerCase();
  switch (name) {
    case 'whisper':
      return new WhisperEngine(options);
    case 'sherpa':
      return new SherpaEngine(options);
    case 'hybrid':
      return new HybridEngine(options);
    case 'vosk':
      throw new Error("Vosk has been deprecated and completely removed in v2.0.0. Please use 'sherpa' (SenseVoice) or 'whisper'.");
    default:
      throw new Error(`Unknown engine: ${engineName}. Available: whisper, sherpa, hybrid`);
  }
}

class TermuxSTT {
  constructor(options = {}) {
    const engineName = options.engine || 'whisper';
    this.engine = createEngine(engineName, options);
  }
  transcribe(filePath, options = {}) {
    return this.engine.transcribe(filePath, options);
  }
  diarize(filePath, options = {}) {
    return this.engine.diarize(filePath, options);
  }
}

module.exports = {
  TermuxSTT,
  createEngine,
  Engine,
  TranscriptResult,
  Segment,
  WhisperEngine,
  SherpaEngine,
  HybridEngine,
  formatTime
};
