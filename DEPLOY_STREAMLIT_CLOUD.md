# Deploy QR Attendance on Streamlit Community Cloud

This keeps the existing Streamlit + Google Sheets MVP. The only deployment change is that the Streamlit server runs on a public cloud URL, so student phones no longer need to connect directly to the teacher's laptop or share the university LAN.

## 0. Files to keep private

Never push these files to GitHub:

- `credentials.json`
- `secret.key`
- `.streamlit/secrets.toml`
- `.env` files

The supplied `.gitignore` excludes them. If either credential file was already committed to a public GitHub repository, removing it in a later commit is not enough: revoke/rotate that Google service-account key and replace it, and regenerate the app signing key.

## 1. Prepare GitHub

1. Create a **private** GitHub repository for this project.
2. Copy the project source into the repository. Include `app.py`, `views/`, `utils/`, and `requirements.txt` plus the updated `.gitignore` and `.streamlit/config.toml`.
3. Do not copy `credentials.json`, `secret.key`, `.venv/`, `__pycache__/`, or `.streamlit/secrets.toml`.
4. Commit and push the source.

From the project root, you can check what Git will upload with:

```bash
git status --short
git check-ignore -v credentials.json secret.key .streamlit/secrets.toml
```

If a sensitive file was already tracked, untrack it before pushing:

```bash
git rm --cached credentials.json secret.key
# Only run this if it is tracked:
# git rm --cached .streamlit/secrets.toml
git add .gitignore
git commit -m "Prepare QR attendance for cloud deployment"
git push
```

## 2. Create the app secrets

The patch includes a helper that reads your local `credentials.json`, asks for the public app URL, Google Sheet URL, and teacher password, then writes a correctly formatted `.streamlit/secrets.toml` (including a new persistent 32-byte signing key):

```bash
python scripts/make_cloud_secrets.py
```

Choose the subdomain you plan to use before running it. For example, if you plan to create `https://qr-attendance-demo.streamlit.app`, enter that exact URL when prompted. Use a unique teacher password of at least 12 characters.

The script does not print the credentials. It writes them to `.streamlit/secrets.toml`, which is excluded by `.gitignore`. **Never commit or share that file.** You will paste its full contents into Streamlit Community Cloud in the next step.

The script requires your existing `credentials.json` in the project root. The service account needs **Editor** access to the target spreadsheet. Copy its `client_email` into the spreadsheet's Share dialog and grant Editor.

If you prefer to prepare secrets manually, use `.streamlit/secrets.example.toml` as a template. The required keys are `PUBLIC_BASE_URL`, `TEACHER_PASSWORD`, `APP_SECRET_KEY` (exactly 64 hexadecimal characters), `SHEET_URL`, and the `[gcp_service_account]` table copied from the service-account JSON.

For local testing, the completed `.streamlit/secrets.toml` is read automatically. You can continue using the local `credentials.json` and `secret.key` fallback instead if you prefer.

## 3. Deploy on Streamlit Community Cloud

1. Open [https://share.streamlit.io/](https://share.streamlit.io/) and sign in with the GitHub account that owns the repository.
2. Select **Create app** -> **Yup, I have an app**.
3. Select the private repository, branch (usually `main`), and main file path `app.py`.
4. Choose a short custom app subdomain, for example `qr-attendance-demo`. The resulting app URL will be `https://qr-attendance-demo.streamlit.app`.
5. Open **Advanced settings**. Select Python **3.11** to match the project's development environment.
6. Paste the entire contents of `.streamlit/secrets.toml` into the **Secrets** field, then save and deploy. Its `PUBLIC_BASE_URL` must exactly match the app URL chosen in step 4.
7. In the app's sharing settings, make it viewable by **Anyone** so students can open the public student check-in URL. Teacher controls remain protected by the teacher password. Do not put student records or credentials in the public repository.

Official deployment guide: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy

## 4. Test before class

1. Open `https://your-app-name.streamlit.app/teacher` on the teacher's laptop.
2. Log in with `TEACHER_PASSWORD`.
3. Enter a class tab name and generate a QR code.
4. Confirm the QR URL shown under the image begins with the same `https://...streamlit.app` base URL.
5. Scan it using a phone connected to university Wi-Fi. Also test with mobile data as a fallback.
6. Submit a test student and verify that the correct Google Sheet tab receives the attendance mark.
7. Generate a second QR and confirm it has a different token. Wait for expiration and confirm the old link is rejected.

## 5. Operational notes and MVP limitations

- Community Cloud apps hibernate after 12 hours without traffic. Visit the app and wait for it to wake before class starts. The first visit after hibernation may show a wake-up screen.
- No university-LAN or spatial check is performed by this hosted MVP. The demo verifies attendance through a short-lived signed QR token, student ID/name validation, and Google Sheets logging. Do not claim it proves the student is physically inside a particular room.
- If the university later provides a server, deploy the same source there and set `PUBLIC_BASE_URL` to the university-hosted HTTPS URL. The code is not tied to the `streamlit.app` domain.
- The student check-in URL contains a secret route and a signed, expiring session token. The `/teacher` route is still reachable from the Internet, so a strong `TEACHER_PASSWORD` is mandatory.
- Streamlit Community Cloud is suitable for an MVP/demo, not a guarantee of production-grade availability or high-concurrency attendance. Test the expected class size before relying on it.
