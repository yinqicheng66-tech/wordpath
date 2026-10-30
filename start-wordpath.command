#!/bin/bash
# Double-click in Finder to start WordPath locally (backend + frontend).
# Close this window or press Control+C to stop.
cd "$(dirname "$0")"
exec ./scripts/dev.sh
