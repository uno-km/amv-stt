/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
export interface EngineOptions {
  model?: string;
  lang?: string;
  device?: 'auto' | 'vulkan' | 'gpu' | 'cpu';
  threads?: number;
  vad?: boolean;
  vadThreshold?: number;
  quantization?: string;
  numSpeakers?: number;
  customModelPath?: string;
  [key: string]: any;
}

export interface Segment {
  start: number;
  end: number;
  text: string;
  speaker?: string;
  confidence?: number;
}

export class TranscriptResult {
  text: string;
  segments: Segment[];
  language?: string;
  duration?: number;
  speakers?: string[];

  toJson(): string;
  toSrt(): string;
  toVtt(): string;
  toRttm(fileId?: string): string;
}

export abstract class Engine {
  options: EngineOptions;
  constructor(options?: EngineOptions);
  abstract transcribe(audioPath: string, options?: any): Promise<TranscriptResult>;
  abstract diarize(audioPath: string, numSpeakers?: number): Promise<TranscriptResult>;
  getInfo(): Record<string, any>;
}

export class WhisperEngine extends Engine {
  transcribe(audioPath: string, options?: any): Promise<TranscriptResult>;
  diarize(audioPath: string, numSpeakers?: number): Promise<TranscriptResult>;
}

export class SherpaEngine extends Engine {
  transcribe(audioPath: string, options?: any): Promise<TranscriptResult>;
  diarize(audioPath: string, numSpeakers?: number): Promise<TranscriptResult>;
}

export class HybridEngine extends Engine {
  transcribe(audioPath: string, options?: any): Promise<TranscriptResult>;
  diarize(audioPath: string, numSpeakers?: number): Promise<TranscriptResult>;
}

export function createEngine(
  engineName?: 'whisper' | 'sherpa' | 'hybrid' | string,
  options?: EngineOptions
): Engine;

export class TermuxSTT {
  engine: Engine;
  constructor(options?: EngineOptions & { engine?: string });
  transcribe(filePath: string, options?: any): Promise<TranscriptResult>;
  diarize(filePath: string, options?: any): Promise<TranscriptResult>;
}
