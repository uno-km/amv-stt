/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * WhisperEngine for Node.js - wraps whisper.cpp via spawn or termux-stt CLI
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { Engine, TranscriptResult, Segment } = require('./engine');

class WhisperEngine extends Engine {
  constructor(config = {}) {
    super(config);
    this.model = config.model || 'base';
    this.lang = config.lang || 'ko';
    this.threads = config.threads || null;
    this.device = config.device || 'auto';
  }

  async transcribe(audioPath, options = {}) {
    return new Promise((resolve, reject) => {
      const device = options.device || this.device || 'auto';
      const model = options.model || this.model || 'base';
      const lang = options.lang || this.lang || 'ko';
      const threads = options.threads || this.threads;

      const args = [
        '-m', 'termux_stt.cli.main',
        'transcribe',
        '--engine', 'whisper',
        '--model', model,
        '--lang', lang,
        '--device', device,
        '--format', 'json',
      ];

      if (threads) {
        args.push('--threads', String(threads));
      }

      args.push(audioPath);

      const pythonExe = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
      const proc = spawn(pythonExe, args, { env: process.env });
      let stdout = '';
      let stderr = '';

      proc.stdout.on('data', (d) => { stdout += d.toString(); });
      proc.stderr.on('data', (d) => { stderr += d.toString(); });

      proc.on('close', (code) => {
        if (code !== 0) {
          return reject(new Error(`whisper transcription failed (code ${code}): ${stderr}`));
        }
        try {
          const parsed = JSON.parse(stdout);
          const segments = (parsed.segments || []).map(
            s => new Segment(s.start, s.end, s.text, s.speaker, s.confidence)
          );
          resolve(new TranscriptResult(parsed.text, segments, parsed.language || lang, parsed.duration));
        } catch (e) {
          // Fallback if stdout was plain text
          resolve(new TranscriptResult(stdout.trim(), [new Segment(0, 0, stdout.trim())], lang));
        }
      });
    });
  }

  getInfo() {
    return {
      name: 'whisper.cpp (Node.js)',
      model: this.model,
      language: this.lang,
      threads: this.threads,
      device: this.device,
    };
  }
}

module.exports = { WhisperEngine };
