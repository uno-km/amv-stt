# Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
# SPDX-License-Identifier: Apache-2.0 OR Commercial-License
import sys

from termux_stt.models.hub import ModelHub
from termux_stt.models.registry import list_models
from termux_stt.exceptions import RuntimeRequiredError


def run_models(args):
    action = args.action

    if action == "list":
        cached = ModelHub.list_cached_models()
        print("=== Cached Local Models ===")
        if not cached:
            print("  (No models currently cached)")
        else:
            for item in cached:
                print(f"  - [{item['engine']}] {item['model_name']}")

        print("\n=== Available Registry Models ===")
        engine_filter = getattr(args, "engine", None)
        for model_entry in list_models(engine_filter):
            desc = f" ({model_entry.get('size', '')}) - {model_entry.get('description', '')}"
            print(f"  - [{model_entry['engine']}] {model_entry['model_name']}{desc}")

    elif action == "download":
        model_name = getattr(args, "model", None)
        engine_name = getattr(args, "engine", "whisper")
        extra_args = getattr(args, "extra_args", [])
        if extra_args:
            if len(extra_args) >= 2:
                engine_name, model_name = extra_args[0], extra_args[1]
            elif len(extra_args) == 1:
                model_name = extra_args[0]

        if not model_name:
            print("[-] Error: Please specify a model name to download with --model <name> or 'models download [engine] <model>'.")
            sys.exit(1)

        print(f"[*] Downloading model '{model_name}' for engine '{engine_name}'...")
        try:
            path = ModelHub.ensure_model(engine_name, model_name)
            print(f"[+] Model successfully downloaded to: {path}")
        except RuntimeRequiredError:
            raise
        except Exception as e:
            print(f"[-] Download failed: {e}")
            sys.exit(1)

    elif action == "remove":
        if not args.model:
            print("[-] Error: Please specify a model name to remove with --model <name>.")
            sys.exit(1)
        engine_name = getattr(args, "engine", "whisper")
        print(f"[*] Removing model '{args.model}' from engine '{engine_name}'...")
        if ModelHub.remove_model(engine_name, args.model):
            print(f"[+] Model '{args.model}' successfully removed from cache.")
        else:
            print(f"[-] Model '{args.model}' was not found in cache.")
