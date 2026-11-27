#!/usr/bin/env bash
# Scanner receives only public source and the image archive.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/check-public.py
mkdir -p private
work=$(mktemp -d "$PWD/private/scan.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT
reports=$(mktemp -d "$PWD/private/security-XXXXXXXX")
mkdir -p "$work/public" private/trivy-cache
git ls-files --cached --others --exclude-standard -z | tar --null -T - -cf - | tar -xf - -C "$work/public"
docker save careerpilot-local:dev -o "$work/image.tar"
scan=(docker run --rm --user "$(id -u):$(id -g)" -v "$work:/scan:ro" -v "$reports:/reports" -v "$PWD/private/trivy-cache:/cache" aquasec/trivy:0.76.2 --cache-dir /cache --quiet)
status=0
"${scan[@]}" fs --format json --output /reports/source.json --scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1 /scan/public || status=1
"${scan[@]}" image --format json --output /reports/image.json --input /scan/image.tar --scanners vuln --severity HIGH,CRITICAL --exit-code 1 || status=1
python3 - "$reports" <<'PYREPORT'
import json,sys
from collections import Counter
from pathlib import Path
for p in sorted(Path(sys.argv[1]).glob("*.json")):
    results=json.loads(p.read_text()).get("Results",[])
    vulns=[v for r in results for v in r.get("Vulnerabilities",[])]
    print(p.stem, dict(Counter(v["Severity"] for v in vulns)), "with published fixes", sum(bool(v.get("FixedVersion")) for v in vulns), "secret findings",sum(len(r.get("Secrets",[])) for r in results))
print("Reports:",sys.argv[1])
PYREPORT
exit "$status"
