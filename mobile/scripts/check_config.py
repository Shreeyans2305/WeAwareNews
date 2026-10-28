"""Reject live mobile configs and credential literals in tracked or staged files."""
import pathlib
import re
import subprocess
import sys

staged = "--staged" in sys.argv
root = pathlib.Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
args = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"] if staged else ["git", "ls-files", "-z", "mobile"]
paths = subprocess.check_output(args, cwd=root).decode().split("\0")
failures = []
for name in filter(None, paths):
    if not name.startswith("mobile/"):
        continue
    if pathlib.Path(name).name in {"Config.local.xcconfig", "google-services.json", "GoogleService-Info.plist"}:
        failures.append(f"{name}: live configuration must remain untracked")
    content = subprocess.check_output(["git", "show", f":{name}"], cwd=root) if staged else (root / name).read_bytes()
    if re.search(rb"AIza[0-9A-Za-z_-]{35}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", content):
        failures.append(f"{name}: credential literal detected")
if failures:
    print("\n".join(failures))
    sys.exit(1)
print("Mobile configuration guard passed")
