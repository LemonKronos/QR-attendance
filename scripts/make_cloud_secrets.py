"""Create .streamlit/secrets.toml from the local Google service-account JSON.

Run from the project root:
    python scripts/make_cloud_secrets.py

The resulting file is ignored by Git. Paste its contents into Streamlit
Community Cloud -> App settings -> Secrets when deploying.
"""

from __future__ import annotations

import getpass
import json
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS_PATH = PROJECT_ROOT / "credentials.json"
SECRETS_DIRECTORY = PROJECT_ROOT / ".streamlit"
SECRETS_PATH = SECRETS_DIRECTORY / "secrets.toml"


def toml_value(value: object) -> str:
    """Serialize JSON-compatible scalar values as valid TOML values."""
    if isinstance(value, (str, int, float, bool)):
        return json.dumps(value, ensure_ascii=False)
    raise TypeError(f"Unsupported service-account field value: {type(value).__name__}")


def main() -> None:
    if not CREDENTIALS_PATH.is_file():
        raise SystemExit(
            "Missing credentials.json in the project root. Download your Google "
            "service-account JSON key and place it there before running this script."
        )

    service_account = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    required_fields = {"type", "project_id", "private_key", "client_email", "token_uri"}
    missing_fields = sorted(required_fields.difference(service_account))
    if missing_fields:
        raise SystemExit("The JSON file is missing required fields: " + ", ".join(missing_fields))
    if service_account.get("type") != "service_account":
        raise SystemExit("credentials.json is not a Google service-account key.")

    print("Create Streamlit Community Cloud secrets")
    print("Choose the final app subdomain first, e.g. qr-attendance-demo.streamlit.app.\n")

    public_url = input("Public app URL (https://...streamlit.app): ").strip().rstrip("/")
    if not public_url.startswith("https://") or not public_url.endswith(".streamlit.app"):
        raise SystemExit("For this MVP, PUBLIC_BASE_URL must be an https://*.streamlit.app URL.")

    sheet_url = input("Google Sheet URL: ").strip()
    if not sheet_url.startswith("https://docs.google.com/spreadsheets/"):
        raise SystemExit("Please enter a valid Google Sheets URL.")

    teacher_password = getpass.getpass("New teacher password: ")
    password_confirmation = getpass.getpass("Confirm teacher password: ")
    if teacher_password != password_confirmation:
        raise SystemExit("The passwords do not match.")

    lines = [
        f"PUBLIC_BASE_URL = {toml_value(public_url)}",
        f"TEACHER_PASSWORD = {toml_value(teacher_password)}",
        f"APP_SECRET_KEY = {toml_value(secrets.token_hex(32))}",
        f"SHEET_URL = {toml_value(sheet_url)}",
        "",
        "[gcp_service_account]",
    ]
    for key, value in service_account.items():
        if value is not None:
            lines.append(f"{key} = {toml_value(value)}")

    SECRETS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if SECRETS_PATH.exists():
        overwrite = input(".streamlit/secrets.toml already exists. Overwrite it? [y/N]: ").strip().lower()
        if overwrite not in {"y", "yes"}:
            raise SystemExit("Cancelled; existing secrets.toml was left unchanged.")

    SECRETS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nCreated .streamlit/secrets.toml")
    print("This file contains private credentials. Do NOT commit or share it.")
    print("Open it locally, then paste its entire contents into Community Cloud -> App settings -> Secrets.")
    print("The script does not print any secret values.")


if __name__ == "__main__":
    main()
