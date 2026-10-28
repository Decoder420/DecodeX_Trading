import os
import re
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent

# 1. Clean logs/2026-10-26/app.log
log_file = repo_root / "logs" / "2026-10-26" / "app.log"
if log_file.exists():
    text = log_file.read_text(encoding="utf-8")
    # Redact X-PrivateKey
    text = re.sub(r"'X-PrivateKey':\s*'[^']+'", "'X-PrivateKey': '[MASKED]'", text)
    # Redact Authorization Bearer
    text = re.sub(r"'Authorization':\s*'Bearer\s+[^']+'", "'Authorization': 'Bearer [MASKED]'", text)
    # Redact refreshToken
    text = re.sub(r"'refreshToken':\s*'[^']+'", "'refreshToken': '[MASKED]'", text)
    # Redact any remaining eyJ... JWTs
    text = re.sub(r"eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}", "[MASKED_JWT]", text)
    log_file.write_text(text, encoding="utf-8")
    print(f"Sanitized {log_file}")

# 2. Remove groww_token.json
groww_token = repo_root / "data" / "cache" / "groww_token.json"
if groww_token.exists():
    groww_token.unlink()
    print(f"Removed {groww_token}")

# 4. Clean task logs in .gemini tasks folder
task_dir = Path("/Users/manan/.gemini/antigravity-ide/brain/4d96eafc-0205-4052-8b6b-6a99cfa18873/.system_generated/tasks")
if task_dir.exists():
    for f in task_dir.glob("*.log"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"'X-PrivateKey':\s*'[^']+'", "'X-PrivateKey': '[MASKED]'", text)
        text = re.sub(r"'Authorization':\s*'Bearer\s+[^']+'", "'Authorization': 'Bearer [MASKED]'", text)
        text = re.sub(r"'refreshToken':\s*'[^']+'", "'refreshToken': '[MASKED]'", text)
        text = re.sub(r"eyJ[a-zA-Z0-9_-]{15,}\.eyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}", "[MASKED_JWT]", text)
        f.write_text(text, encoding="utf-8")
        print(f"Sanitized task log: {f.name}")

