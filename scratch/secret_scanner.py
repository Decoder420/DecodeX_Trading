import os
import re
import sys
from pathlib import Path

# Load secrets from .env safely
repo_root = Path(__file__).resolve().parent.parent
env_path = repo_root / ".env"

secrets_to_check = []
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'\''")
                if len(v) >= 4 and any(s in k.upper() for s in ["KEY", "SECRET", "PIN", "CLIENT", "CODE", "TOKEN"]):
                    secrets_to_check.append((k, v))

# Regex for JWT-like tokens (header.payload.signature)
jwt_pattern = re.compile(r"eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}")

# Directories to scan
scan_targets = [
    repo_root,
    Path("/Users/manan/.gemini/antigravity-ide/brain/4d96eafc-0205-4052-8b6b-6a99cfa18873/.system_generated/tasks"),
]

# Excluded paths
excluded_names = {".env", ".git", ".venv", "__pycache__", "node_modules"}

leaks_found = []
files_scanned = 0

for target in scan_targets:
    if not target.exists():
        continue
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in excluded_names]
        for fname in files:
            if fname in excluded_names:
                continue
            fpath = Path(root) / fname
            # Skip binary files that are not duckdb or parquet
            ext = fpath.suffix.lower()
            try:
                # Read content as bytes/text
                content = fpath.read_bytes()
                files_scanned += 1
                
                # Check for each secret
                for key_name, secret_val in secrets_to_check:
                    secret_bytes = secret_val.encode("utf-8")
                    if secret_bytes in content:
                        leaks_found.append({
                            "file": str(fpath),
                            "matched_type": f"Environment secret [{key_name}]",
                            "count": content.count(secret_bytes),
                        })
                
                # Check for JWT strings
                try:
                    text_content = content.decode("utf-8", errors="ignore")
                    jwt_matches = jwt_pattern.findall(text_content)
                    if jwt_matches:
                        leaks_found.append({
                            "file": str(fpath),
                            "matched_type": "JWT-like token pattern",
                            "count": len(jwt_matches),
                        })
                except Exception:
                    pass
            except Exception:
                continue

print("==================================================")
print("SECRET AND CREDENTIAL SCAN REPORT")
print("==================================================")
print(f"Total files scanned across repo & tasks: {files_scanned}")
print(f"Total leak instances detected: {len(leaks_found)}")
if leaks_found:
    print("\nLEAK DETAILS (Values omitted):")
    for item in leaks_found:
        print(f"  - File: {item['file']}")
        print(f"    Type: {item['matched_type']} (occurrences: {item['count']})")
else:
    print("\nRESULT: CLEAN. Zero secret or JWT leaks detected anywhere in repo or task logs.")
print("==================================================")
