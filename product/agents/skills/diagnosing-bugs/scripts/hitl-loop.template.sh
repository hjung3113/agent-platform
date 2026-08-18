#!/usr/bin/env bash
# Generic human-in-the-loop reproduction loop.
# Copy this file, edit only the scenario section, and run it.
set -euo pipefail

step() {
  printf '\n>>> %s\n' "$1"
  read -r -p "    [Enter when done] " _
}

capture() {
  local var="$1" question="$2" answer
  printf '\n>>> %s\n' "$question"
  read -r -p "    > " answer
  printf -v "$var" '%s' "$answer"
}

# --- edit scenario below -----------------------------------------------
step "Perform the single manual action required to trigger the bug."
capture REPRODUCED "Did the exact reported symptom occur? (y/n)"
capture OBSERVATION "Enter the minimal redacted observation needed to classify the result:"
# --- edit scenario above -----------------------------------------------

printf '\n--- Captured ---\n'
printf 'REPRODUCED=%s\n' "$REPRODUCED"
printf 'OBSERVATION=%s\n' "$OBSERVATION"
