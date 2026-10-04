# Application Notebook · Local Job Application Tracker

[简体中文](README.md) | **English**

Track the companies and roles you have applied to in a browser on your Windows computer. No account, internet connection, or database installation is required for everyday use. The application runs on the Python standard library.

## Starting and stopping

1. Open the project folder. On the original development computer, it is `D:\Study\Master\JobApplicationTracker`. If you cloned the repository elsewhere, use your own checkout location.
2. Double-click **`start.bat`**. Your browser will open <http://127.0.0.1:8765>.
3. Keep the launcher window open; you can minimize it. Starting again opens the existing instance rather than creating a separate set of records.
4. Double-click **`stop.bat`**, or press `Ctrl+C` in the launcher window, to stop the service. Closing the browser tab does not stop it.

Python 3.10 or newer is required. The application has been tested on Windows with Python 3.13.13 and Microsoft Edge. No `pip install` command is needed for normal use.

You can also start it in PowerShell from the project folder:

```powershell
cd D:\Study\Master\JobApplicationTracker
python app.py
```

If another application is using the default port:

```powershell
python app.py --port 8766
# Stop the instance on this port when finished:
python app.py --stop --port 8766
```

The service listens only on `127.0.0.1`; other computers on your local network cannot access it. Page content, styles, and scripts are all local. There are no external fonts, analytics, or cloud storage. Opening a saved job URL takes you to that external website.

## Chinese and English versions

- This file is the complete English counterpart of [README.md](README.md). Keep both documents in sync when making documentation changes.
- Click **English / 中文** at the top right to switch the interface. The first visit defaults to Chinese; subsequent visits remember this browser's choice. Switching reloads the page.
- You can also open Chinese directly at <http://127.0.0.1:8765/?lang=zh> or English at <http://127.0.0.1:8765/?lang=en>.
- Both languages cover headings, buttons, forms, search results, categories, duplicate warnings, application error messages, and backup workflows. Browser-native date controls, file pickers, and validation messages follow the browser/operating-system language.
- Both interfaces share one database. User-entered company names, job titles, and other personal content are never automatically translated or rewritten. Chinese company aliases remain searchable in the English interface.
- Interface and server messages are paired in `static/locales/zh.json` and `static/locales/en.json`, with matching keys and parameters. Add an English translation whenever adding a Chinese message.
- In `companies.json`, `scope_en`, `category_en`, and `provenance_en` provide English counterparts to the Chinese fields. Company names, source URLs, and search aliases are shared rather than duplicated in a second company list.
- Python/JavaScript business logic remains a single shared implementation using language resources, avoiding divergent language-specific copies. Tests check matching language keys, parameters, and translation coverage for static page text.

## Recording and searching applications

- Click **Record application** (`记录新申请`) and enter a **company name and job title**. The job URL is optional; if provided, it must be a full `https://` or `http://` address.
- The application date defaults to today according to your computer's browser. You can change it to the actual submission date.
- The company field accepts existing names, common Chinese/English aliases, and new companies. A new company is added to the directory only after you save an application.
- Enter just a company name in the search bar to see the roles you have applied to there. Search is case-insensitive, ignores leading/trailing whitespace, and supports partial names and predefined aliases. For example, both `英伟达` and `nvidia` find NVIDIA.
- Select a company in the left panel to view its applications. Use **Filter job titles** (`筛选岗位名称`) in the right panel to check a particular role.
- Companies without saved applications show **No applications to this company yet** (`尚未申请该公司`). Being in the preset directory does not count as having applied.
- Saving the same company and job title triggers a duplicate warning. If it is a different hiring batch or a separate application, select the confirmation checkbox to save it anyway.
- Each record supports editing, deletion, and opening its job URL. Deletion requires confirmation.
- Press `/` to focus the company search bar. Press `Esc` to close a dialog.

Company matching uses Unicode normalization, case normalization, whitespace normalization, and predefined aliases. Google / Alphabet and Amazon / AWS are grouped by familiar employer names; separately listed recruiting brands such as GitHub remain separate. The application does not guess misspellings or merge arbitrary similar names.

## Application status

- New applications and records saved before the status feature was introduced default to `reviewing`.
- The waiting period is the difference in calendar days between the **application date** and the computer's current local date. At 30 days it remains `reviewing`; at 31 days or more it automatically displays `long reviewing`. Older applications entered retrospectively use their actual application date.
- Change the **Application status** (`申请状态`) dropdown on a record to `refused` or `accepted`; the change saves immediately. Status is also editable in the application form.
- `refused` and `accepted` remain unchanged as time passes. Switching back to `reviewing` restores automatic date-based classification: applications older than 30 days display `long reviewing` again.
- `long reviewing` is calculated automatically for applications still awaiting review. It is not a manual selection. Changing an application date recalculates the displayed status.
- Status is recalculated whenever you open or refresh the page. An open page checks for a new date every minute and when returning from the background or computer sleep. You do not need to keep the application running for 30 days.

The status upgrade adds a database column while preserving existing record IDs, companies, titles, URLs, and dates.

## Company directory

The bundled directory contains **300 candidate company/recruiting-brand names**, covering AI / ML, software and cloud computing, chips and computer hardware, robotics and autonomous driving, and internet, fintech, and security companies. Both large employers and early-stage startups are included.

- **275 entries** were manually curated as US technology job-search candidates. Their current operation, independent legal status, and hiring status have not been individually verified.
- **25 US early-stage AI/ML entries** and their locations were extracted from [Y Combinator's official Machine Learning company directory](https://www.ycombinator.com/companies/industry/machine-learning). Each retains a link to its official YC company profile.
- [Nasdaq technology index materials](https://www.nasdaq.com/NDXT) were consulted when compiling large technology/chip companies. These references do not individually verify all 300 entries.
- The directory includes subsidiaries, acquired companies, and familiar recruiting brands. Its US scope is intended for job searching, not as a legal-domicile database. Inclusion does not indicate that a company is currently hiring, and the list is not exhaustive.
- Directory data is stored in `companies.json`. The `provenance` / `provenance_en` fields explain its source, and `aliases` provides alternative names. Runtime access is entirely offline.
- You can add an unlisted company by saving an application. Preset directory entries never create application records by themselves.

`scripts/build_company_catalog.py` is a development-time generation script requiring internet access and `beautifulsoup4`; ordinary users do not need to run it. Regeneration updates the JSON file only. Existing company entries in the database are not overwritten. Back up data and use a database migration when changing existing company aliases; do not delete the user database to update the directory.

## Data and backups

Data is stored in `data/applications.sqlite3` inside the project folder. On the original development computer, the full path is:

```text
D:\Study\Master\JobApplicationTracker\data\applications.sqlite3
```

Records are stored in this SQLite file, not in the browser cache. Restarting the application, shutting down the computer, or clearing browser cache does not delete it. Keep the `data` folder.

Open **Backup & restore** (`备份与恢复`):

1. **Download backup** (`下载备份`) exports a JSON file containing all applications, including company, title, URL, application date, creation time, status, and record ID. Save a separate copy somewhere safe.
2. **Choose backup file** (`选择备份文件`) previews the number of records. Nothing is written until you confirm the merge.
3. New records are added; records with an identical ID and content are skipped.
4. If a record with the same ID has since been edited, the entire import is canceled with a conflict message so an older backup cannot overwrite newer changes.
5. An invalid file or record rolls back the entire import. There are no partial imports. The limits are 20 MB and 50,000 records.

JSON backups restore applications and their associated custom companies. They do not include custom companies that no longer have any applications, nor historical versions of the preset directory. To preserve the complete database exactly, stop the service and copy the entire `data` folder. For database-level restoration, stop the service and keep a copy of the current database before replacing `applications.sqlite3`.

The current backup format is version 2 and includes manual status. Applications awaiting review are stored as `reviewing`; after restoration, their application dates determine whether to display `long reviewing`. Version 1 backups remain supported: newly restored records default to `reviewing`; existing records whose other fields match are skipped, preserving their current manual status. A status conflict in a version 2 backup cancels the entire import. Older application versions cannot import version 2 backups.

## Validation

Backend tests use the Python standard library and require no additional dependencies:

```powershell
python -m unittest discover -s tests -v
```

Browser acceptance scripts require the development dependency `playwright` and an installed copy of Microsoft Edge:

```powershell
python -m pip install playwright
python tests/browser_check.py
python tests/browser_status_check.py
python tests/browser_language_check.py
```

Browser tests use temporary databases. They cover first launch, the company directory, Chinese aliases, creating applications, duplicate warnings and confirmation, editing, job-title filtering, no-record search results, page reloads, delete confirmation, backup download/restoration, invalid backups, and narrow-window layouts. Status tests cover the 30/31-day boundary, automatic updates on an open page, manual results, persistence, and resetting automatic review. Screenshots are saved in `test-results/`; test records are never written to the real database.

Language tests cover English workflows, remembered language choice, shared bilingual data, application validation messages, and narrow-window layouts.

## Project structure

```text
README.md                     Chinese documentation
README_EN.md                  English documentation
app.py                        Local HTTP server, SQLite storage, input validation
localization.py               Server translations and bilingual catalog fields
start.bat / stop.bat           Windows start/stop entry points
companies.json                300 company candidates and source notes
static/                       Local page, styling, and interactions
static/locales/               Paired Chinese/English language resources
data/applications.sqlite3     Actual application data (created on first launch)
tests/                        Backend and browser acceptance checks
scripts/                      Directory generation utilities
```

If the page cannot connect, restart the service and refresh. If changed files do not appear, press `Ctrl+F5`. This is a single-user local application; it does not provide cloud sync, automatic job scraping, or automatic job applications.
