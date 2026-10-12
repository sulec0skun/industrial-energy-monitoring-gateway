# Release Checklist

## Local final checks

- [ ] Stop simulator, gateway, subscriber, and Streamlit before changing demo settings.
- [ ] Confirm the main database is `energy_monitoring`, not `energy_monitoring_live_test`.
- [ ] Restore the original simulator checkpoint if a temporary test checkpoint was used.
- [ ] Confirm `data/telemetry_sample.csv` is included and readable.
- [ ] Confirm `requirements.txt` was generated from the project's working virtual environment.
- [ ] Check `schema.sql` with a fresh **separate** database, or verify the existing table schema.
- [ ] Confirm the dashboard opens and can read stored records.
- [ ] Confirm `verify_telemetry.py` reports a complete run against the **main** database after successful replay.

## Git and privacy

- [ ] `.env` is NOT staged or tracked; `.env.example` contains placeholders only.
- [ ] `.venv/`, Python caches, logs, and `data/simulator_state*.json` are NOT staged or tracked.
- [ ] No passwords, PostgreSQL backups, personal screenshots, or private files are included.
- [ ] `data/telemetry_sample.csv` and `DATA_ATTRIBUTION.md` ARE included.
- [ ] Use `git status` and `git diff --cached --name-only` to review before committing.
- [ ] Confirm `git check-ignore .env` and `git check-ignore data/simulator_state.json` show ignored paths.
- [ ] Push the repository only after reviewing its staged file list.

## Reviewer experience

- [ ] README describes dependency installation and PostgreSQL/Mosquitto startup.
- [ ] README includes SQL schema creation, `.env` configuration and run order.
- [ ] README explains the finite replay, timestamps, and deduplication behavior.
- [ ] README includes a clean verification command.
- [ ] Optional: add a screenshot of the dashboard without private credentials.
