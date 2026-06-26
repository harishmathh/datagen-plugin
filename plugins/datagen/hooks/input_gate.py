#!/usr/bin/env python3
"""DataGen input-gate hook (UserPromptSubmit).

Safe and non-destructive. It only ever ADDS a short context note; it never
blocks the prompt, edits anything, or calls out to the network.

When the user's prompt looks like a request to research a domain or generate a
dataset, it reminds Claude that the DataGen skills need a business context and an
objective before they do anything (comments are optional). That keeps the
required-input gate enforced consistently across runs and saves a back-and-forth.

The hook reads the UserPromptSubmit event JSON on stdin and, if it decides to
say something, prints a small JSON object that adds context. Otherwise it exits
quietly. Any error is swallowed so a hook problem can never break a prompt.
"""
import json
import sys

# Words that suggest the user wants research or a dataset out of DataGen.
TRIGGERS = (
    "dataset", "datagen", "synthetic data", "fake data", "mock data",
    "test data", "sample data", "research the", "research a", "research my",
    "dataset-research", "dataset-generator", "generate data",
    "customer base", "segment", "ground the numbers",
)

NOTE = (
    "DataGen reminder: the Dataset-Research and Dataset-Generator skills both "
    "require a BUSINESS CONTEXT and an OBJECTIVE before they do anything "
    "(additional comments are optional). If either is missing or vague from the "
    "user's message, ask for it and wait. Dataset-Research is research only and "
    "ends with a visual HTML report; Dataset-Generator runs the full pipeline "
    "and calls Dataset-Research for grounding."
)


def main() -> int:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # never break the prompt

    prompt = str(event.get("prompt", "")).lower()
    if not prompt:
        return 0

    if any(t in prompt for t in TRIGGERS):
        out = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": NOTE,
            }
        }
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        # Absolutely never let a hook failure surface to the user.
        raise SystemExit(0)
