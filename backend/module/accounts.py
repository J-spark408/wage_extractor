import os, json, secrets

ACCOUNTS_FILE = os.path.join(os.getcwd(), "accounts.json")

def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        return {}
    with open(ACCOUNTS_FILE, "r") as f:
        return json.load(f)

def save_accounts(accounts: dict):
    tmp_path = ACCOUNTS_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(accounts, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, ACCOUNTS_FILE)

# NEW: generate a fresh 6-digit PIN (leading zeros allowed)
def generate_pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"
