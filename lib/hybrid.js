/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * HybridEngine for Node.js - Vosk X-Vector Diarization + Whisper STT
 */

const { spawn } = require('child_process');
const { Engine, TranscriptResult, Segment } = require('./engine');

class HybridEngine extends Engine {
  constructor(config = {}) {
    super(config);
    this.model = config.model || 'base';
    this.lang = config.lang || 'ko';
    this.numSpeakers = config.numSpeakers || 2;
  }

  async transcribe(audioPath, options = {}) {
    return this.diarize(audioPath, this.numSpeakers);
  }

  async diarize(audioPath, numSpeakers = 2) {
    return new Promise((resolve, reject) => {
      const args = [
        '-m', 'termux_stt.cli.main',
        'diarize',
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
          return reject(new Error(`Hybrid diarization failed (code ${code}): ${stderr}`));
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
      name: 'Hybrid Neural Diarizer + Whisper (Node.js)',
      model: this.model,
      language: this.lang,
      numSpeakers: this.numSpeakers
    };
  }
}

module.exports = { HybridEngine };
