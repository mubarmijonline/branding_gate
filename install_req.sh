#!/bin/bash

REQ_FILE="req.txt"
LOG_FILE="install_log.txt"


cd /projects/branding_gate
echo "Starting installation from $REQ_FILE" > "$LOG_FILE"
echo "--------------------------------------" >> "$LOG_FILE"

while IFS= read -r package || [[ -n "$package" ]]; do
    echo "Installing: $package"
    if pip install "$package"; then
        echo "[SUCCESS] $package" >> "$LOG_FILE"
    else
        echo "[FAILED]  $package" >> "$LOG_FILE"
    fi
done < "$REQ_FILE"

echo "--------------------------------------" >> "$LOG_FILE"
echo "Done. Check $LOG_FILE for details."
