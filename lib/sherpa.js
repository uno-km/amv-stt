/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * SherpaEngine for Node.js - Non-Autoregressive SenseVoice STT & Neural Diarization
 */

const { spawn } = require('child_process');
const { Engine, TranscriptResult, Segment } = require('./engine');

class SherpaEngine extends Engine {
  constructor(config = {}) {
    super(config);
    this.model = config.model || 'sensevoice-small-int8';
    this.lang = config.lang || 'ko';
    this.threads = config.threads || 4;
  }

  async transcribe(audioPath, options = {}) {
    return new Promise((resolve, reject) => {
      const args = [
        '-m', 'termux_stt.cli.main',
        'transcribe',
        '--engine', 'sherpa',
        '--model', this.model,
        '--lang', this.lang,
        '--format', 'json',
        audioPath
      ];

      const proc = spawn('python', args, { env: process.env });
      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (d) => { stdout += d.toString(); });
      proc.stderr.on('data', (d) => { stderr += d.toString(); });

      proc.on('close', (code) => {
        if (code !== 0) {
          return reject(new Error(`Sherpa transcription failed (code ${code}): ${stderr}`));
        }
        try {
          const parsed = JSON.parse(stdout);
          const segments = (parsed.segments || []).map(
            s => new Segment(s.start, s.end, s.text, s.speaker, s.confidence)
          );
          resolve(new TranscriptResult(parsed.text, segments, parsed.language || this.lang, parsed.duration));
        } catch (e) {
          resolve(new TranscriptResult(stdout.trim(), [new Segment(0, 0, stdout.trim())], this.lang));
        }
      });
    });
  }

  async diarize(audioPath, numSpeakers = 2) {
    return new Promise((resolve, reject) => {
      const args = [
        '-m', 'termux_stt.cli.main',
        'diarize',
        '--engine', 'sherpa',
        '--speakers', String(numSpeakers),
        '--format', 'json',
        audioPath
      ];

      const proc = spawn('python', args, { env: process.env });
      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (d) => { stdout += d.toString(); });
      proc.stderr.on('data', (d) => { stderr += d.toString(); });

      proc.on('close', (code) => {
        if (code !== 0) {
          return reject(new Error(`Sherpa diarization failed (code ${code}): ${stderr}`));
        }
        try {
          const parsed = JSON.parse(stdout);
          const segments = (parsed.segments || []).map(
            s => new Segment(s.start, s.end, s.text, s.speaker, s.confidence)
          );
          resolve(new TranscriptResult(parsed.text, segments, parsed.language || this.lang, parsed.duration));
        } catch (e) {
          resolve(new TranscriptResult(stdout.trim(), [new Segment(0, 0, stdout.trim())], this.lang));
        }
      });
    });
  }

  getInfo() {
    return {
      name: 'Sherpa-ONNX (Node.js)',
      model: this.model,
      language: this.lang,
      threads: this.threads
    };
  }
}

module.exports = { SherpaEngine };
