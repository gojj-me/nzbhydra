#!/bin/bash
set -eu
ROOT=/config/nzbhydra-maintenance
if ! python "$ROOT/updater/maintenance.py" boot; then
    # This legacy image logs custom-init errors but otherwise starts stock code.
    # Prevent an unverified or interrupted selection from silently starting it.
    for service_dir in /etc/services.d/hydra /var/run/s6/services/hydra; do
        if [ -d "$service_dir" ]; then
            printf '#!/bin/sh\necho "Maintenance recovery required; application not started" >&2\nexec sleep 3600\n' > "$service_dir/run"
            chmod 755 "$service_dir/run"
        fi
    done
    exit 1
fi
