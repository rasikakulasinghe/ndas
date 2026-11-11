# NDAS Live QA, CRUD, Performance, UI & Security Audit Report

- **Date:** 2026-10-23
- **Target Environment:** `https://demo.ndas.lk` (requested as `www.demo.ndas.lk`)
- **Test Account:** `rasikakulasinghe` (User ID `1`, `user_type=SUPERADMIN`, `is_superuser=True`, `is_staff=True`)
- **Active Test Scope:** Multi-Institution Superadmin Scope + Switched Context (`Institution ID 1` — Lady Ridgeway Hospital for Children, slug `lady-ridgeway-hospital`)
- **Server Stack Observed:** Cloudflare CDN (`cf-ray`, HTTP/3) $\rightarrow$ LiteSpeed / Phusion Passenger 6.2.0 $\rightarrow$ Django 6.0 / Python WSGI (`MULTI_INSTITUTION_ENABLED=True`, `DEBUG=False`)
- **Live Data Hygiene:** All temporary QA records created during end-to-end CRUD testing (`Patient #44` / `QA999991`, `HINE #16`, `CDIC #11`, `DA #13`, `GPA`, `Problem`, and `Bookmark #21`) were verified and permanently deleted via the live API (`GET /patient/view/44/` verified `404 Not Found`). Pre-existing demo records were left untouched.

---

## 1. Executive Summary

A full-stack live QA evaluation (automated Playwright headless Chromium inspection, authenticated HTTP crawling of 100+ routes, end-to-end live CRUD lifecycle verification, and static codebase auditing) uncovered **48 distinct issues** across infrastructure, CRUD workflows, security/isolation, performance, UI/CSP, and form validation:

| Severity | Count | Key Highlights |
| :--- | :---: | :--- |
| **CRITICAL (P0)** | **9** | `www.demo.ndas.lk` DNS failure; **100% of `/media/` files broken** (`X-Accel-Redirect` unhandled by Passenger); **random session logouts** (`LocMemCache` + cache sessions across Passenger workers); **5 live HTTP 500 crashes** (`/print/`, `/users/activity/`, `/users/send-verification/`, multi-match `/search/results/`, `/problems/analysis/?patient=abc`); cross-institution IDOR in `userEdit`; unescaped XML in ReportLab PDF generator |
| **HIGH (P1)** | **15** | `added_by` / `last_edit_by` never set on HINE, CDIC, DA, GPA, Problem & Bookmark edits (breaks staff delete permissions & shows `"Unknown"` on timeline); `SUPERADMIN` blocked (`404`) from viewing/deleting own bookmarks; `owner` vs `added_by` mismatch in Bookmark checks; `MultipleObjectsReturned` crash when 2 users bookmark the same item; wrong model field names in Referral snapshots & Excel/PDF exports; CSP blocking inline JS on Patient Move, Backup Create & Report History |
| **MEDIUM (P2)** | **14** | Severe N+1 queries in `patient_manager` (9 extra SQL queries per abnormal patient row), `gpa_manager`, and `video_manager`; synchronous `ip-api.com` HTTP calls on every login; Bootstrap 4 vs HTMX notification dropdown event mismatch; jQuery `$` called before `jquery.min.js` loads; BHT/NNC search validator rejecting valid alphanumeric identifiers |
| **LOW (P3)** | **10** | Stray `>` in sidebar markup; `{{getCorrectedAge}}` literal text in dashboard HTML; UTF-8 replacement character (``) in page titles; `POG_WKS` missing weeks 43–44; duplicate `PatientMoveLog` audit entries |

---

## 2. Critical Infrastructure, DNS, Media Delivery & Session Failures (P0)

### 2.1. [INFRA-01] `www.demo.ndas.lk` Fails DNS Resolution (`NXDOMAIN`)
- **Severity:** CRITICAL (P0)
- **Live Reproduction:**
  - `GET https://www.demo.ndas.lk` fails immediately with `socket.gaierror: [Errno 11001] getaddrinfo failed` (`NXDOMAIN`).
  - Only the apex subdomain `https://demo.ndas.lk` resolves (`104.21.84.205` / `172.67.194.203` behind Cloudflare).
- **Root Cause:** Missing `CNAME` or `A`/`AAAA` DNS record for `www.demo` in the `ndas.lk` Cloudflare DNS zone, even though [DEPLOYMENT.md](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/DEPLOYMENT.md#L298) documents `https://www.demo.ndas.lk` as a valid host.
- **Fix:** Add a Cloudflare `CNAME` record for `www.demo` pointing to `demo.ndas.lk` and ensure `www.demo.ndas.lk` is included in `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in production `.env`.

---

### 2.2. [INFRA-02] 100% of Media Files (`/media/...` — Videos, Attachments, Logos, Avatars) Fail in Production
- **Severity:** CRITICAL (P0)
- **Code References:**
  - [`protected_media_view`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L909-L963)
  - [`InstitutionContextMiddleware`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/middleware.py#L17-L29)
  - [`ndas/urls.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/urls.py#L57-L61)
- **Live Reproduction:**
  1. On `/institution/` (before selecting an institution), the two institution logo images request:
     - `GET /media/lady-ridgeway-hospital/logo/cropped-1766149242335.png`
     - `GET /media/nh-kandy/logo/PP04.JPG`
     Both return **`302 Found` $\rightarrow$ `Location: /institution/`** (`Content-Type: text/html`, 8,708 bytes).
  2. After switching into Institution 1 (`POST /institution/switch/1/`), requesting any media asset (logos, attachments, or video streams such as `/media/2025/11/sample_video_01_bG0dc2a.mp4`) returns **`404 Not Found`** (`Content-Type: text/html`, 9,838 bytes — Django's 404 page).
- **Root Cause:**
  1. In [`protected_media_view`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L957-L963), when `settings.DEBUG` is `False`, Django does not stream the file; instead it returns an empty `HttpResponse` with header `X-Accel-Redirect: /x-accel-media/{quote(path)}`.
  2. The live server runs **LiteSpeed / Phusion Passenger 6.2.0** (cPanel shared/VPS hosting), not a custom Nginx server with an `internal; location /x-accel-media/ { alias ...; }` block.
  3. Passenger intercepts the internal redirect to `/x-accel-media/<path>` and routes it **back into the Django WSGI application**:
     - When `SUPERADMIN` has `active_institution_id = None` (on `/institution/`), [`InstitutionContextMiddleware.EXEMPT_URLS`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/middleware.py#L17-L29) exempts `/media/` but **not** `/x-accel-media/`, so middleware redirects `/x-accel-media/...` to `302 /institution/`.
     - **Compounding Rate-Limit Side Effect:** Every single visit to `/institution/` triggers 2 extra redirected `GET /institution/` requests from the broken `<img>` tags (3 hits per page load), exhausting the `10/m` rate limit on [`institution_selector`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L51) after just 3 refreshes (`429 Too Many Requests`).
     - When an institution **is** active (`active_institution_id = 1`), `/x-accel-media/<path>` passes middleware and hits [`ndas/urls.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/urls.py), matches no URL pattern, and returns a Django `404` HTML page.
- **Fix:**
  - Add an environment setting `USE_X_ACCEL_REDIRECT = os.environ.get("USE_X_ACCEL_REDIRECT", "False").lower() == "true"` (or `USE_X_SENDFILE` for LiteSpeed/Apache `X-LiteSpeed-Location` / `X-Sendfile`).
  - When `USE_X_ACCEL_REDIRECT` is `False` (such as on Passenger/LiteSpeed without an internal `/x-accel-media/` block), serve the file via Django's `FileResponse(open(full_path, 'rb'), content_type=content_type)` with HTTP Range support for video streaming.

---

### 2.3. [INFRA-03] Random Session Logouts in Production (`LocMemCache` + Cache Session Backend Under Multi-Worker Passenger)
- **Severity:** CRITICAL (P0)
- **Code References:** [`ndas/settings.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/settings.py#L405-L440)
- **Live Reproduction:**
  - Observed live during Playwright and HTTP crawling: when Phusion Passenger spawns a second worker process or recycles an idle process, an authenticated request with a valid `sessionid` cookie suddenly receives:
    `HTTP 302 Found -> Location: /users/login/?next=...` with `Set-Cookie: sessionid=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/`, wiping the user's browser session cookie.
- **Root Cause:**
  - In [`ndas/settings.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/settings.py#L422-L440), when `DEBUG=False` and `REDIS_URL` is not set:
    ```python
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'ndas-production-cache',
            'TIMEOUT': 300,
            'OPTIONS': {'MAX_ENTRIES': 1000}
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    ```
  - `LocMemCache` is **process-local memory**. Each Passenger worker process has its own isolated Python memory space. Whenever a request lands on a different worker process, `LocMemCache` misses the session key, Django treats the session as non-existent, and `SessionMiddleware` deletes the client's `sessionid` cookie.
  - Additionally, `TIMEOUT: 300` (5 minutes) and `MAX_ENTRIES: 1000` can evict active sessions prematurely.
  - Furthermore, if `REDIS_URL` **is** configured later, [`ndas/settings.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/settings.py#L409-L416) specifies `'BACKEND': 'django.core.cache.backends.redis.RedisCache'` alongside `django-redis`-only `OPTIONS` (`CLIENT_CLASS`, `COMPRESSOR`, `IGNORE_EXCEPTIONS`), which raises `TypeError` on startup, and neither `redis` nor `django-redis` is pinned in [`requirements.txt`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/requirements.txt).
- **Fix:**
  - When `REDIS_URL` is not configured, set `SESSION_ENGINE = 'django.contrib.sessions.backends.db'` (or `cached_db`) so sessions persist in PostgreSQL/SQLite across all Passenger workers.

---

## 3. Live HTTP 500 Server Crashes & Broken Endpoints (P0)

Every endpoint below was verified live on `https://demo.ndas.lk`:

| # | Endpoint | Method | Live Status | Exception / Root Cause | Code Location |
| :- | :--- | :---: | :---: | :--- | :--- |
| **3.1** | `/print/` | `GET` | **500** (`0.14s`) | `ValueError: The view patients.views.print didn't return an HttpResponse object` — stub view `def print(request): pass` is linked directly from Dashboard "Patients $\rightarrow$ More info" card. | [`patients/views.py:3594-3596`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3594-L3596), [`templates/patients/index.html:56`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/index.html#L56) |
| **3.2** | `/users/activity/` | `GET` | **500** (`0.18s`) | `TemplateDoesNotExist: base.html` — template uses `{% extends 'base.html' %}` and `{% block content %}` instead of `{% extends 'src/base.html' %}` and `{% block main_content %}`. | [`templates/users/user_activity.html:1,24`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/users/user_activity.html#L1-L24), [`users/views.py:428`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L428) |
| **3.3** | `/users/send-verification/` & `/users/verify-email/<expired>/` | `GET` | **500** (`0.22s`) | `TemplateDoesNotExist: base.html` — both templates use `{% extends 'base.html' %}` instead of `{% extends 'src/base.html' %}`. | [`templates/users/send_verification.html:1`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/users/send_verification.html#L1), [`templates/users/verification_expired.html:1`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/users/verification_expired.html#L1) |
| **3.4** | `/search/results/` (when >1 patient matches) | `POST` | **500** (`0.18s`) | `NoReverseMatch: Reverse for 'delete-confirm-patient' not found` — `results.html` calls removed URL `{% url 'delete-confirm-patient' Patient.id %}` and non-existent field `{{ Patient.clinic_no }}`. | [`templates/patients/results.html:36,51`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/results.html#L36-L51), [`patients/views.py:813`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L813) |
| **3.5** | `/problems/analysis/?patient=abc` & `/problems/analysis/export/?patient=abc` | `GET` | **500** (`0.14s`) | `ValueError: Field 'id' expected a number but got 'abc'` — `problem_analysis` and `problem_analysis_export` pass unvalidated `request.GET.get('patient')` to `.filter(patient_id=patient_id)`. | [`problemlist/views.py:480-481,553-554`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/problemlist/views.py#L480-L554) |
| **3.6** | `/debug/bootstrap/` | `GET` | **500** (`0.16s`) | `TemplateDoesNotExist: debug_bootstrap.html` — route is mounted in production [`ndas/urls.py:39`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/urls.py#L39) and renders a non-existent template. | [`ndas/views.py:37`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/views.py#L37), [`ndas/urls.py:39`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/urls.py#L39) |

---

## 4. CRUD Operations Matrix & Data Integrity Defects

### 4.1. End-to-End Live CRUD Verification Matrix

| Module / Entity | Create (`POST`) | Read (`GET` List & Detail) | Update (`POST`) | Delete (`DELETE` w/ Password) | Live Status & Defects Found |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Patients** | PASS (`200`, ID `44`) | PASS (`200`) | PASS (`200`) | PASS (`200` JSON) | Search multi-match crashes (`500`); single-match renders broken `view.html` missing context; BHT/NNC search rejects alphanumeric strings. |
| **Videos** | FAIL (Media 404) | PARTIAL (Page `200`, stream `404`) | PASS (Metadata) | PASS (Superuser) | Video playback 100% broken in production (`X-Accel-Redirect` 404); `video_view` calls removed `video.is_new_file()` method (`AttributeError` swallowed, always `True`). |
| **GMA Assessments** | PASS | PASS (`200`, ID `1`) | PASS | PASS | Referral snapshot uses wrong fields (`gma.conclusion`, `gma.age_of_record`). Excel export uses non-existent `age_at_assessment_weeks`. |
| **HINE Assessments** | PASS (`200`, ID `16`) | PASS (`200`) | PASS (`200`) | FAIL for Staff (`added_by=None`) | `hine_assessment_add`/`edit` never set `added_by`/`last_edit_by`. Staff cannot delete records they created (`has_delete_permission` checks `added_by == user`). Timeline shows `"assessor": "Unknown"`. |
| **CDIC Records** | PASS (`200`, ID `11`) | PASS (`200`) | PASS (`200`) | FAIL for Staff (`added_by=None`) | `cdic_assessment_add`/`edit` never set `added_by`/`last_edit_by`. Timeline shows `"assessor": "Unknown"`. |
| **Developmental (DA)** | PASS (`200`, ID `13`) | PASS (`200`) | PASS (`200`) | FAIL for Staff (`added_by=None`) | `da_assessment_add`/`edit` never set `added_by`/`last_edit_by`. PDF export omits 2 of 4 clinical domains (`hsl_*`, `seb_*`). Excel export leaves 6 columns blank. |
| **GPA Assessments** | PASS (`200`) | PASS (`200`, IDs `1,3`) | PASS (`200`) | FAIL for Staff (`added_by=None`) | `gpa_add`/`edit` never set `added_by`/`last_edit_by`. `discharged_authorized_by` leaks all 9 users across all institutions. `delete_helpers.py` checks `'GPARecord'` instead of `'GeneralPaediatricAssessment'`. |
| **Attachments** | PASS | PARTIAL (Page `200`, file `404`) | BUGGY | PASS | File preview/download returns `404` (`X-Accel-Redirect`). `attachment_edit` fails to re-extract `file_size`/`mime_type`/`original_filename` on file replacement and renders unbound form on error. |
| **Problem List** | PASS (`200`) | PASS (`200`) | PASS (`200`) | PASS (`200`) | `problem_status_change` and `problem_action_add` do not update `last_edit_by`. Invalid `?patient=abc` on `/problems/analysis/` crashes with `500`. |
| **Bookmarks** | PASS (`200`, ID `21`) | **FAIL (`404` for Superadmin)** | **FAIL (`404` for Superadmin)** | **FAIL (`404` for Superadmin)** | Superadmin bookmarks return `404` on view/delete when switched into an institution (`owner__institution` is `None`). `get_bookmarked_object_url()` fails for `Video`, `HINE`, `DA`, `CDICR`, `GPA`. `is_bookmarked` crashes with `MultipleObjectsReturned` when 2 users bookmark the same item. |
| **Referrals** | PASS | PASS (`200`) | PASS | N/A | Clinical snapshot builder [`referral/utils.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/referral/utils.py#L84-L95) accesses non-existent fields on GMA and HINE. |
| **Institutions & Move** | PASS | PASS (`200`) | PASS (`200`) | N/A | Patient Move button (`#execute-btn`) is permanently disabled in browser because `<script>` lacks CSP `nonce`. Visiting `/institution/` clears `active_institution_id`, breaking `/users/` and `/backup/` links. |
| **Users & Admin** | PASS | PASS (`200`) | PASS (`200`) | PASS | `/users/edit/<pk>/` (`userEdit`) has a cross-institution IDOR for staff admins. `/users/activity/` and `/users/send-verification/` crash with `500`. |
| **Reports (PDF/Excel)** | PASS (`200`) | PASS (`200`) | N/A | FAIL (CSP blocks JS) | ReportLab `Paragraph()` receives unescaped clinical text (XML injection / crash risk). History delete button broken by missing CSP `nonce`. |

---

### 4.2. Detailed CRUD & Business Logic Defects

#### [CRUD-01] `added_by` and `last_edit_by` Omitted Across 11 Create/Update Views — Breaks Staff Delete Permissions & Audit Trail
- **Severity:** HIGH (P1)
- **Code References:**
  - [`patients/views.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py):
    - `cdic_assessment_add` ([lines 2356–2358](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L2356-L2358)) & `cdic_assessment_edit` ([lines 2410–2411](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L2410-L2411))
    - `hine_assessment_add` ([lines 2773–2775](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L2773-L2775)) & `hine_assessment_edit` ([lines 2819–2820](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L2819-L2820))
    - `da_assessment_add` ([lines 3165–3167](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3165-L3167)) & `da_assessment_edit` ([lines 3219–3221](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3219-L3221))
    - `gpa_add` ([lines 3613–3615](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3613-L3615)) & `gpa_edit` ([lines 3648–3649](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3648-L3649))
    - `bookmark_edit` ([lines 1765–1766](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L1765-L1766))
  - [`problemlist/views.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/problemlist/views.py):
    - `problem_status_change` ([line 364](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/problemlist/views.py#L364)) & `problem_action_add` ([line 428](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/problemlist/views.py#L428))
  - [`ndas/custom_codes/delete_helpers.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/delete_helpers.py#L51-L54)
- **Impact (Verified Live):**
  1. [`UserActivityMiddleware`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/middleware.py#L24-L53) does **not** auto-populate `added_by` or `last_edit_by` on model saves.
  2. When a non-superuser staff clinician creates a HINE, CDIC, DA, or GPA record, `added_by` is stored as `NULL` (`None`).
  3. [`has_delete_permission`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/delete_helpers.py#L51-L54) checks `if hasattr(entity, 'added_by') and entity.added_by == user: return True`. Because `entity.added_by` is `None`, **staff users receive `403 Permission denied` when attempting to delete HINE, CDIC, DA, or GPA records they personally created**.
  4. On the Patient Timeline (`/patient/view/<pk>/`), [`get_patient_timeline_events`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/timeline_utils.py#L215-L318) displays `"by Unknown"` and `"added_by": "Unknown"` for all newly created HINE, DA, CDIC, and GPA records (verified live on Patient 44: `{"provider": "Dr. QA Tester", "added_by": "Unknown"}`).

---

#### [CRUD-02] Bookmark System Broken Across 4 Layers (`SUPERADMIN` 404 Lockout, `owner` vs `added_by` Mismatch, `MultipleObjectsReturned`, Broken URL Reversal)
- **Severity:** HIGH (P1)
- **Live Verification & Code References:**
  1. **`SUPERADMIN` Cannot View or Delete Any Bookmark (`HTTP 404`)**:
     - [`bookmark_view`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L1568) and [`bookmark_delete`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L1615) query:
       `get_object_or_404(Bookmark, id=pk, **institution_scope(request, 'owner__institution'))`
     - A `SUPERADMIN` user (`rasikakulasinghe`) has `user.institution = None`. When switched into Institution 1 (`request.institution = Institution(1)`), `institution_scope(request, 'owner__institution')` filters by `owner__institution=Institution(1)`.
     - Because `bookmark.owner.institution` is `None`, **every single bookmark owned by `rasikakulasinghe` (existing IDs `1, 2, 3, 6, 8, 9, 10, 11` and newly created ID `21`) immediately returns `404 Not Found` on `/bookmarks/view/<pk>/` and `/bookmarks/delete/<pk>/`**!
     - And if `rasikakulasinghe` clears their active institution by visiting `/institution/`, `InstitutionContextMiddleware` blocks `/bookmarks/view/<pk>/` and `/bookmarks/delete/<pk>/` with `302 Redirect -> /institution/`.
  2. **`owner` vs `added_by` Mismatch (Bookmark Status Always `False`):**
     - [`bookmark_add`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L1476-L1482) sets `owner=request.user` and leaves `added_by=None`.
     - However, [`PatientQuerySet.with_status_annotations`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L82-L87), [`VideoQuerySet.with_bookmark_status`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/models.py#L36-L40), [`Video.get_bookmark_for_user`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/models.py#L381-L386), [`video_view`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/views.py#L125), and [`video_manager`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/views.py#L319) all filter `Bookmark.objects.filter(..., added_by=user)` instead of `owner=user`, so bookmarked patients and videos never show as bookmarked!
  3. **Unhandled `MultipleObjectsReturned` Crash When Two Users Bookmark the Same Record:**
     - [`Patient.isBookmarked`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L603), [`GMAssessment.is_bookmarked`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L987), [`CDICRecord.is_bookmarked`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L1276), [`GeneralPaediatricAssessment.is_bookmarked`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L1548), and [`Attachment.is_bookmarked`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L1981) call `Bookmark.objects.get(bookmark_type=..., object_id=self.pk)` without filtering by `owner`, catching only `Bookmark.DoesNotExist`. As soon as two users bookmark the same record, viewing the detail/manager page crashes with **HTTP 500 (`MultipleObjectsReturned`)**.
  4. **Broken URL Reversal in [`Bookmark.get_bookmarked_object_url()`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L2374-L2395):**
     - Passes `kwargs={"pk": self.object_id}` for every bookmark type and maps `"Video": "file-view"`.
     - However, `"file-view"` does not exist (`"video:view"` expects `video_id`), `"hine-assessment-view"` expects `hine_id`, `"da-assessment-view"` expects `da_id`, `"cdic-assessment-view"` expects `cdic_id`, and `"gpa-view"` expects `gpa_id`.
     - `NoReverseMatch` is silently swallowed and returns `None`, so the "View Bookmarked Item" button disappears on `/bookmarks/view/<pk>/` for all Video, HINE, DA, CDIC, and GPA bookmarks.

---

#### [CRUD-03] Patient Search (`POST /search/results/`) Multi-Match Crash (`500`), Pagination `405`, and Single-Match Broken Context
- **Severity:** CRITICAL (P0)
- **Code References:**
  - [`patients/views.py:661-817`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L661-L817)
  - [`templates/patients/results.html:36,51`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/results.html#L36-L51)
- **Live Reproduction:**
  1. **Multi-Match Crash (`500`):** Submitting `POST /search/results/` with `search_by="Baby Name"`, `search_text="a"` matches multiple patients and renders [`templates/patients/results.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/results.html), which calls `{% url 'delete-confirm-patient' Patient.id %}` (line 51, removed URL) and `{{ Patient.clinic_no }}` (line 36, removed attribute), crashing with `500 Internal Server Error`.
  2. **Pagination `405 Method Not Allowed`:** `search_results` is decorated with `@require_POST` ([line 661](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L661)), so clicking any pagination link (`GET /search/results/?page=2`) returns `405 Method Not Allowed`.
  3. **Single-Match Broken Detail View:** When `search_results` finds exactly 1 matching patient ([lines 711, 729, 747, 768, 807](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L711-L807)), it calls `render(request, "patients/view.html", {"patient": var_patient, "pgn": pagn})` instead of `redirect("view-patient", pk=var_patient.id)`. Because none of the context variables from [`patient_view`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L384-L470) (`videos`, `gma_assessments`, `hine_assessments`, `da_assessments`, `cdic_records`, `gpa_records`, `problems`, `timeline_events`, `delete_url`, `bookmark`) are passed, the rendered patient page appears completely empty of clinical records!

---

#### [CRUD-04] Removed `Video.is_new_file()` Method Called in `video_view`
- **Severity:** MEDIUM (P2)
- **Code References:**
  - [`video/views.py:131`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/views.py#L131)
  - [`templates/video/view.html:231`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/video/view.html#L231)
  - [`templates/patients/view.html:675`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/view.html#L675)
- **Details:** `Video.is_new_file` was removed in favor of `VideoQuerySet.with_assessment_status()` (which annotates `is_new_file_annotated` / property `is_new`). However, [`video_view`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/views.py#L131) still calls `video.is_new_file()` inside a `try/except Exception:` block that always catches `AttributeError` and sets `is_new_file = True`. Consequently, `/video/view/<id>/` always displays the **"Assess Video"** button even for already-assessed videos, while `/patient/view/<pk>/` (`video.is_new_file`) always evaluates to `False`, hiding the **"New"** badge.

---

#### [CRUD-05] Wrong Model Field Names in Referral Snapshots, Excel Exports, PDF Exports, and `delete_helpers.py`
- **Severity:** HIGH (P1)
- **Code References & Impact:**
  1. **Referral Snapshot Builder ([`referral/utils.py:84-95`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/referral/utils.py#L84-L95)):**
     - Accesses `getattr(gma, 'conclusion', '')` (actual field on `GMAssessment`: `diagnosis_conclusion`, which is a ManyToManyField to `DiagnosisList`, or `diagnosis_other`) and `str(getattr(gma, 'age_of_record', ''))` (actual property: `assessment_age`).
     - Accesses `getattr(hine, 'total_score', None)` (actual field on `HINEAssessment`: `score`).
     - **Impact:** Referred clinicians receive snapshots where GMA conclusions, GMA ages, and HINE scores are blank/`None`.
  2. **Excel Export Generator ([`reports/utils/excel_generator.py:453-454,485-486,524-529`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/utils/excel_generator.py#L453-L529)):**
     - Reads `getattr(gma, 'age_at_assessment_weeks', '')` and `age_at_assessment_days` (neither exists on `GMAssessment` or `HINEAssessment`).
     - Reads `getattr(da, 'language_age_from', '')`, `language_age_to`, `language_details`, `social_age_from`, `social_age_to`, `social_details` (actual fields on `DevelopmentalAssessment`: `hsl_age_from`, `hsl_age_to`, `hsl_details`, `seb_age_from`, `seb_age_to`, `seb_details`).
     - **Impact:** 6 columns in the Developmental Assessment Excel sheet and 2 columns in the GMA/HINE sheets are permanently blank.
  3. **Developmental Assessment PDF Export ([`reports/utils/pdf_generator.py:526-561`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/utils/pdf_generator.py#L526-L561)):**
     - `DAAssessmentPDFGenerator` only renders Gross Motor (`gm_*`) and Fine Motor & Vision (`fmv_*`) and completely omits Hearing, Speech & Language (`hsl_*`) and Social, Emotional & Behavioural (`seb_*`).
  4. **Unescaped Clinical Text Passed to ReportLab `Paragraph()` ([`reports/utils/pdf_generator.py:251,357,398,457,517,596,693`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/utils/pdf_generator.py#L251-L693)):**
     - User-entered clinical text (`diagnosis_other`, `comment`, `assessment`, `today_interventions`, `current_problems`, `physical_examination`) is interpolated directly into `Paragraph(f"<b>...</b> {text}", ...)` without `xml.sax.saxutils.escape()`. Any clinical note containing `<32 weeks` or malformed `<tag>` syntax crashes ReportLab's XML parser with a `ValueError` (`500`) or allows ReportLab XML tag injection.
  5. **Wrong Class Name `'GPARecord'` in [`ndas/custom_codes/delete_helpers.py:171,230,293`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/delete_helpers.py#L171-L293):**
     - `entity.__class__.__name__` is `'GeneralPaediatricAssessment'`, not `'GPARecord'`. All three branches are dead code, falling back to generic display names and redirect URLs.
  6. **Duplicate `PatientMoveLog` Creation ([`institution/views.py:612-626`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L612-L626)):**
     - `superadmin_patient_move` calls `move_patient(patient, target_institution, performed_by=request.user, notes=reason)` (which already creates a `PatientMoveLog` inside [`institution/utils.py:72`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/utils.py#L72)) and then immediately calls `PatientMoveLog.objects.create(...)` a second time, recording two duplicate audit rows per move.
  7. **`attachment_edit` Ignores Replaced File Metadata & Renders Unbound Form on Error ([`patients/views.py:2174-2189`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L2174-L2189)):**
     - [`Attachment.save()`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L1812-L1816) only extracts `file_size`, `mime_type`, and `original_filename` when `is_new` is `True` or `"attachment" in kwargs.get("update_fields", [])`. Because `attachment_edit` calls `var_attachment.save()` without `update_fields`, replacing a file leaves stale metadata from the old file. Also, on POST validation failure, line 2188 renders the unbound `a_form` instead of `a_form_data`, wiping user input and field error messages.

---

#### [CRUD-06] Superadmin Institution Context Cleared on `/institution/`, Breaking Navigation to `/users/`, `/backup/`, and `/institution/settings/`
- **Severity:** HIGH (P1)
- **Code References:**
  - [`institution/views.py:68,733-741`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L68)
  - [`institution/middleware.py:17-29,93`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/middleware.py#L17-L93)
- **Live Reproduction:**
  1. Whenever a `SUPERADMIN` visits `GET /institution/` (`institution_selector`), [line 68](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L68) executes `request.session.pop('active_institution_id', None)`.
  2. From the `/institution/` page, clicking **Profile**, **User Management** (`/users/admin/users/`), or **Backup** (`/backup/`) in the top navbar/sidebar hits [`InstitutionContextMiddleware`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/middleware.py#L17-L29). Because neither `/users/` nor `/backup/` is in `EXEMPT_URLS` (only `/users/login/` and `/users/logout/` are exempt), the middleware immediately redirects the `SUPERADMIN` back to `302 /institution/`.
  3. Conversely, `/institution/settings/` **does** match `EXEMPT_URLS` (`'/institution/'` prefix at [line 19](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/middleware.py#L19)), so `InstitutionContextMiddleware` returns early **before** setting `request.institution`! When a `SUPERADMIN` (switched into Institution 1) visits `GET /institution/settings/`, [`_get_admin_institution`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L733-L741) reads `getattr(request, 'institution', None)` which is `None`, and redirects the `SUPERADMIN` away to `302 /` (`home`)! (Verified live: `GET /institution/settings/` $\rightarrow$ `302 /`).

---

## 5. Security & Multi-Institution Isolation Vulnerabilities

### 5.1. [SEC-01] Cross-Institution IDOR in `userEdit` (`/users/edit/<pk>/`)
- **Severity:** CRITICAL (P0)
- **Code References:** [`users/views.py:250-296`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L250-L296)
- **Details:**
  - While `userView` and `admin_user_edit` use [`get_institution_scoped_user_or_404`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L39-L64), `userEdit` at [line 251](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L251) uses an unscoped `user = get_object_or_404(CustomUser, id=pk)` followed by:
    ```python
    if request.user.id != user.id and not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You do not have permission to edit this user's profile.")
        return redirect("home")
    ```
  - Because institution admins have `is_staff=True` (`is_superuser=False`), any institution admin can send `GET/POST /users/edit/<pk>/` for a user belonging to **another institution** and view or overwrite their profile details, email, phone numbers, and position.
- **Fix:** Replace `get_object_or_404(CustomUser, id=pk)` in `userEdit` with `get_institution_scoped_user_or_404(request, id=pk)`.

---

### 5.2. [SEC-02] Cross-Institution User Enumeration in `GeneralPaediatricAssessmentForm` (`discharged_authorized_by`)
- **Severity:** HIGH (P1)
- **Code References:** [`patients/forms.py:1022-1029`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/forms.py#L1022-L1029)
- **Live Verification:**
  - On `GET /gpa/add/44/` and `GET /gpa/edit/1/` (while scoped to Institution 1, which has 6 users), the `<select name="discharged_authorized_by">` dropdown rendered **9 options** (all active users across every institution in the database).
- **Root Cause:** `GeneralPaediatricAssessmentForm.__init__` sets:
  `self.fields["discharged_authorized_by"].queryset = CustomUser.objects.filter(is_active=True).order_by("first_name", "last_name", "username")` with no institution filter.
- **Fix:** Pass `institution=getattr(request, 'institution', None)` into `GeneralPaediatricAssessmentForm` and filter `queryset` by `institution`.

---

### 5.3. [SEC-03] Cross-Institution Data Leak in `admin_dashboard` (`/users/admin/dashboard/`)
- **Severity:** HIGH (P1)
- **Code References:** [`users/views.py:564-614`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L564-L614)
- **Details:** Unlike `admin_user_list` ([line 628](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L628)) and `admin_activity_logs` ([line 903](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L903)), `admin_dashboard` queries `CustomUser.objects.count()`, `UserActivityLog.objects.select_related('user').order_by('-timestamp')[:10]`, and `CustomUser.objects.order_by('-date_joined')[:5]` **without** scoping to `request.institution`. A non-superuser institution admin visiting `/users/admin/dashboard/` sees recent users and login activity from all other institutions.

---

### 5.4. [SEC-04] Global `unique=True` Constraints on Patient Identifiers Across Institutions
- **Severity:** MEDIUM (P2)
- **Code References:**
  - [`patients/models.py:158-194`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L158-L194) (`bht`, `nnc_no`, `pt_reg_no`, `pin`, `pc_no`, `disk_no`)
  - [`patients/forms.py:38-65`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/forms.py#L38-L65) (`_check_unique_field` uses `Patient.objects.all_institutions()`)
- **Details:** Hospital bed head ticket numbers (`bht`, e.g., `12345`) and clinic numbers (`nnc_no`) frequently collide across independent hospitals (e.g., Lady Ridgeway Hospital vs Teaching Hospital Peradeniya). Enforcing global `unique=True` across all institutions prevents Institution B from registering a patient whose BHT number happened to be used at Institution A, and leaks cross-institution existence via validation errors (`"A patient with this BHT already exists"`). These should use `UniqueConstraint(fields=['institution', '<field>'], condition=~Q(<field>__isnull=True) & ~Q(<field>=''))`.

---

## 6. Performance Bottlenecks & N+1 Query Analysis

### 6.1. Live Response Time Measurements (`https://demo.ndas.lk`)

| Route | Purpose | Live Latency | Status | Bottleneck Identified |
| :--- | :--- | :---: | :---: | :--- |
| `GET /users/login/` (Cold Start) | Initial Passenger worker wakeup | **7.65s** | `200` | Passenger WSGI cold spawn + heavy imports |
| `POST /users/login/` | User authentication | **0.87s – 2.10s** | `302` | 2 synchronous HTTP calls to `http://ip-api.com/json/{ip}` |
| `GET /` | Main Institution Dashboard | **0.35s – 0.45s** | `200` | 15+ aggregate count queries + `SubscriptionCheckMiddleware` |
| `GET /manager/patient/` | Patient Manager (11 patients) | **0.23s – 0.31s** | `200` | **9 extra SQL queries per abnormal patient row** (`getDiagnosisList`) |
| `GET /reports/pdf/patient/2/` | Patient PDF Generation | **0.30s** | `200` | Synchronous ReportLab build in WSGI worker thread |
| `GET /institution/superadmin/` | Superadmin Overview | **0.20s** | `200` | Per-institution loop queries |

---

### 6.2. Code-Level Performance & Scalability Bottlenecks

#### [PERF-01] 2 Synchronous External HTTP Calls to `http://ip-api.com` on Every Login
- **Severity:** MEDIUM (P2)
- **Code References:** [`users/utils.py:47-105,137,209`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/utils.py#L47-L105)
- **Details:** During [`loginPage`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L142-L149), Django calls both `log_user_activity()` and `create_or_update_user_session()`. Each function calls `get_location_from_ip(ip_address)`, which makes an uncached, synchronous `requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)` over **unencrypted HTTP**.
- **Impact:** Adds `0.8s` to `10.0s` of blocking latency to every login, leaks clinician IP addresses to a third-party service over plain HTTP, and fails when `ip-api.com` rate-limits (45 req/min).

#### [PERF-02] Severe N+1 Queries in `patient_manager` (`9` Extra Queries per Abnormal Patient Row)
- **Severity:** MEDIUM (P2)
- **Code References:**
  - [`templates/patients/manager.html:352`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/manager.html#L352)
  - [`patients/models.py:553-595`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L553-L595) (`Patient.getDiagnosisList`)
  - [`patients/views.py:248`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L248)
- **Details:**
  1. In [`templates/patients/manager.html:352`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/manager.html#L352), for every abnormal patient in the table, the template evaluates `{{Patient.getDiagnosisList.0}} {{Patient.getDiagnosisList.1}} {{Patient.getDiagnosisList.2}}`.
  2. `Patient.getDiagnosisList` is a `@property` without `@cached_property` that executes `self.gm_assessments.last()`, `self.hine_assessments.last()`, and `self.developmental_assessments.last()` (3 SQL queries) on **each** property access $\times 3$ accesses = **9 SQL queries per abnormal patient row** (up to 225 extra queries per 25-row page).
  3. Additionally, [`patient_manager`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L248) calls `getPatientList(pts_type, institution=_inst)` without passing `user=request.user`, so `is_bookmarked_annotated` is not annotated.

#### [PERF-03] N+1 Queries & In-Memory Filtering Across Assessment & Video Managers
- **Severity:** MEDIUM (P2)
- **Code References:**
  - [`patients/views.py:3736,3784`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3736-L3784) (`gpa_manager` & `gpa_manager_by_patient`): Loop over all GPA records on the page and run `gpa.is_bookmarked` (1 query per row).
  - [`video/views.py:255,376,420`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/views.py#L255-L420) (`video_manager*`): Do not chain `.with_assessment_status()` or `.with_bookmark_status(request.user)`, triggering per-row `GMAssessment.objects.filter(video_file=self).exists()` queries in templates.
  - [`patients/views.py:3298,3409`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L3298-L3409) (`da_assessment_manager*`): Evaluates `[da.id for da in assessments_list if ...]` in Python memory before pagination when `age_range` is filtered.

#### [PERF-04] Per-Request Database Overhead (`SESSION_SAVE_EVERY_REQUEST = True` & Uncached `SubscriptionCheckMiddleware`)
- **Severity:** MEDIUM (P2)
- **Code References:**
  - [`ndas/settings.py:53-54,365`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/settings.py#L53-L54)
  - [`users/middleware.py:56-107`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/middleware.py#L56-L107)
- **Details:**
  - `SESSION_SAVE_EVERY_REQUEST = True` forces a session write on every HTTP request, including the background HTMX notification poll (`GET /institution/notifications/count/`) that fires every 60 seconds in every open browser tab.
  - Both `SubscriptionCheckMiddleware` (which queries `Subscription.get_global_subscription()` from the DB without caching) and `InstitutionContextMiddleware` run on every authenticated request.

#### [PERF-05] Synchronous `moviepy` / `ffprobe` Video Processing Inside HTTP Request Cycle
- **Severity:** MEDIUM (P2)
- **Code References:** [`video/models.py:237-283,308-330`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/video/models.py#L237-L330)
- **Details:** `Video.save()` synchronously spawns `moviepy.VideoFileClip` / `ffprobe` to inspect video duration and resolution inside the HTTP upload request thread, risking Cloudflare `524 A Timeout Occurred` (100s limit) on large clinical videos (up to 2 GB allowed).

---

## 7. UI, Content Security Policy (CSP), JavaScript & Template Defects

### 7.1. [UI-01] Strict CSP Blocks Inline `<script>` Tags Missing `nonce="{{ request.csp_nonce }}"` (Breaks Key Features)
- **Severity:** HIGH (P1)
- **Root Cause:** `CSP_SCRIPT_SRC = ("'self'",)` with `CSP_INCLUDE_NONCE_IN = ['script-src']` ([`ndas/settings.py:527-534`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/settings.py#L527-L534)) blocks any `<script>` tag lacking `nonce="{{ request.csp_nonce }}"` and any inline event attribute (`onclick=`, `onchange=`).
- **Broken Pages & Features (Verified in Live DOM):**
  1. **Patient Move Permanently Disabled (`/institution/patient-move/<pk>/`):**
     - [`templates/institution/superadmin_patient_move.html:206`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/institution/superadmin_patient_move.html#L206) has a bare `<script>` tag without `nonce`. Because the `#execute-btn` button starts with `disabled` in HTML and relies on that inline script to enable it when `#target_institution` and `#confirm-check` change, **Superadmins cannot click "Execute Move" in any modern browser**!
  2. **Backup Scope Selector Broken (`/backup/create/`):**
     - [`backup/templates/backup/create.html:118`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/backup/templates/backup/create.html#L118) has a bare `<script>` without `nonce`, and lines [81, 89, 97](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/backup/templates/backup/create.html#L81-L97) use `onchange="toggleInstitutionSelect()"` — both blocked by CSP.
  3. **Report History Delete Button Broken (`/reports/history/`):**
     - [`reports/templates/reports/history.html:135`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/templates/reports/history.html#L135) has a bare `<script>` without `nonce`. Clicking `.delete-report-btn` does nothing.
  4. **Report Builder Field Select/Clear Buttons Broken (`/reports/`):**
     - [`reports/templates/reports/builder.html:297,300,408,419,422`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/templates/reports/builder.html#L297-L422) use inline `onclick="togglePatientSubfields(true)"` and `onclick="toggleFieldSection(...)"`, which are blocked by CSP.
  5. **Advanced Search Panel Broken on All Manager Pages:**
     - [`templates/src/advance_search.html:56,84,173`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/src/advance_search.html#L56-L173) uses `onchange="toggleScoreFields(this.value)"` and `onclick="resetAdvancedSearch()"`, blocked by CSP.
  6. **Patient Search Helper Script Blocked (`/search/`):**
     - [`templates/patients/search.html:51`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/search.html#L51) has `<script>` without `nonce`.

---

### 7.2. [UI-02] `ReferenceError: $ is not defined` (Scripts Placed Inside `main_content` Before `jquery.min.js`)
- **Severity:** MEDIUM (P2)
- **Code References:**
  - [`templates/src/basic_plane.html:46-52`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/src/basic_plane.html#L46-L52) (loads `jquery.min.js` **after** `{% block main_content %}`)
  - [`templates/src/advance_search.html:224,287`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/src/advance_search.html#L224-L287)
  - [`templates/attachment/edit.html:210`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/attachment/edit.html#L210) & [`templates/attachment/view.html:401`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/attachment/view.html#L401)
  - [`templates/bookmark/view.html:195`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/bookmark/view.html#L195)
- **Details:** These templates place `<script nonce="{{ request.csp_nonce }}">$(document).ready(...)</script>` inside `{% block main_content %}` instead of `{% block extra_js %}`. Because `jquery.min.js` is loaded at the bottom of `basic_plane.html` after `main_content`, `$` is undefined when the script executes. In addition, `attachment/edit.html` and `attachment/view.html` reference `bsCustomFileInput` and `toastr`, neither of which is loaded in `basic_plane.html`.

---

### 7.3. [UI-03] Notification Bell Dropdown Stuck on `"Loading notifications…"` (Bootstrap 4 jQuery Event vs HTMX Native Event)
- **Severity:** MEDIUM (P2)
- **Code References:** [`templates/src/navbar.html:119-128`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/src/navbar.html#L119-L128)
- **Details:** The notification menu uses `hx-get="{% url 'institution:notification-dropdown' %}"` with `hx-trigger="show.bs.dropdown from:closest .nav-item once"`. In **Bootstrap 4.6**, `show.bs.dropdown` is dispatched exclusively via jQuery (`$(...).trigger('show.bs.dropdown')`), **not** as a native DOM `CustomEvent`. Because HTMX listens via native `addEventListener`, `show.bs.dropdown` never triggers HTMX, leaving the dropdown permanently stuck on `"Loading notifications…"` when clicked (`click once` on the toggle link should be used instead).

---

### 7.4. [UI-04] Visual, Markup & Character Encoding Glitches (Live Verified)
- **Severity:** LOW (P3)
- **Code References:**
  1. **Stray `>` Character in Left Sidebar on Every Page:** [`templates/src/main_sidebar_menu.html:79`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/src/main_sidebar_menu.html#L79) has a duplicate closing bracket (`class="d-block">>`) right below the logged-in user's position badge.
  2. **Literal `{{getCorrectedAge}}` Text & Broken `> 10` List Comparison on Dashboard (`/`):**
     - [`templates/patients/index.html:25`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/index.html#L25) has `<div class="row"{{getCorrectedAge}}>`.
     - [`templates/patients/index.html:243`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/index.html#L243) compares a QuerySet to an integer (`{% if Patients_new_list_10 > 10 %}` instead of `{% if Patients_new_list_10|length >= 10 %}`), which always evaluates to `False`, permanently hiding the `"View All"` footer link.
  3. **Corrupted UTF-8 Replacement Character (`\ufffd` / ``) in Page `<title>` Tags:**
     - Verified live on `/referral/inbox/` (`"Referrals  NDAS"`), `/referral/initiate/2/` (`"Refer Patient  NDAS"`), and `/institution/patient-move/2/` (`"Move Patient  NDAS"`): [`templates/referral/inbox.html:4`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/referral/inbox.html#L4), [`templates/referral/initiate.html:4`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/referral/initiate.html#L4), [`templates/institution/superadmin_patient_move.html:4`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/institution/superadmin_patient_move.html#L4).

---

## 8. Input Validation & Schema Mismatches

### 8.1. [VAL-01] BHT & NNC Search Validation Rejects Alphanumeric Identifiers Allowed by `PatientForm`
- **Severity:** HIGH (P1)
- **Code References:**
  - [`patients/forms.py:176,357`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/forms.py#L176-L357) (allows letters, numbers, spaces, hyphens, slashes, e.g. `BHT/2026/01` or `NNC-104`)
  - [`ndas/custom_codes/validators.py:307-350`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/validators.py#L307-L350) (`BHT_validation` & `NNC_validation`)
  - [`patients/views.py:699,735`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L699-L735) (`search_results`)
- **Live Reproduction:**
  - Creating a patient with `bht="QA999991"` succeeds in `PatientForm` (`POST /patient/add/`).
  - Searching for `search_by="BHT"`, `search_text="QA999991"` on `POST /search/results/` fails with error: `"BHT number can only contain numbers and spaces."` because `BHT_validation` ([line 307](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/validators.py#L307)) and `NNC_validation` ([line 335](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/validators.py#L335)) enforce `.isnumeric()`!

---

### 8.2. [VAL-02] `POG_WKS` Dropdown Choice Tuple Missing Weeks `43` and `44`
- **Severity:** LOW (P3)
- **Code References:**
  - [`ndas/custom_codes/choice.py:62-86`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/choice.py#L62-L86) (`POG_WKS` stops at `(42, 42)`)
  - [`patients/forms.py:563`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/forms.py#L563) & [`ndas/custom_codes/validators.py:583`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/validators.py#L583) (allow `20` to `44` weeks)
- **Details:** Post-term infants born at 43 or 44 weeks gestation cannot be selected in the `pog_wks` dropdown even though the model and form validators explicitly permit `20–44` weeks.

---

### 8.3. [VAL-03] `Patient.mo_delivery` Model Default (`"NVD"`) Is Invalid in `MODE_OF_DELIVERY` Choices
- **Severity:** LOW (P3)
- **Code References:**
  - [`patients/models.py:256`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L256) (`default="NVD"`)
  - [`ndas/custom_codes/choice.py:39-46`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/custom_codes/choice.py#L39-L46) (`MODE_OF_DELIVERY` uses `"Normal vaginal delivery (NVD)"`)
- **Details:** Any `Patient` instantiated in code using the default `mo_delivery` fails `full_clean()` with `ValidationError: Value 'NVD' is not a valid choice`.

---

## 9. Prioritized Remediation Roadmap

### Phase 1 — Immediate Production Blockers (Deploy First)
1. **Fix Media Delivery on Passenger ([`institution/views.py:957-963`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/institution/views.py#L957-L963)):** Serve media via Django `FileResponse` when `USE_X_ACCEL_REDIRECT` is not enabled on the web server, restoring all videos, attachments, and logos immediately.
2. **Fix Random Session Logouts ([`ndas/settings.py:422-440`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/ndas/settings.py#L422-L440)):** Switch `SESSION_ENGINE` from `'django.contrib.sessions.backends.cache'` to `'django.contrib.sessions.backends.db'` when `REDIS_URL` is unset.
3. **Add `www.demo.ndas.lk` DNS Record:** Add Cloudflare `CNAME` `www.demo` $\rightarrow$ `demo.ndas.lk`.
4. **Fix All 5 Live HTTP 500 Routes:**
   - Replace `{% extends 'base.html' %}` with `{% extends 'src/base.html' %}` and `{% block content %}` with `{% block main_content %}` in [`user_activity.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/users/user_activity.html), [`send_verification.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/users/send_verification.html), and [`verification_expired.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/users/verification_expired.html).
   - Fix [`templates/patients/results.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/results.html#L36-L51) (`nnc_no` and unified delete modal) and redirect single-match searches in [`search_results`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py#L711-L807) to `redirect("view-patient", pk=var_patient.id)`.
   - Validate `patient_id.isdigit()` in [`problemlist/views.py:480,553`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/problemlist/views.py#L480-L554).
   - Point Dashboard's `/print/` link in [`templates/patients/index.html:56`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/index.html#L56) to `{% url 'manage-patients' %}` and remove or implement `patients.views.print`.
5. **Patch Cross-Institution IDOR & Data Leaks:**
   - Use `get_institution_scoped_user_or_404` in [`userEdit`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L251).
   - Scope `discharged_authorized_by` queryset in [`GeneralPaediatricAssessmentForm`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/forms.py#L1025) and queries in [`admin_dashboard`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/views.py#L564-L595).

### Phase 2 — High-Priority CRUD, CSP & Export Fixes
1. **Populate `added_by` / `last_edit_by` Across All Assessment & Problem Views:** Update HINE, CDIC, DA, GPA, Bookmark, and Problem create/edit views in [`patients/views.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/views.py) and [`problemlist/views.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/problemlist/views.py).
2. **Unify Bookmark Ownership & URL Resolution:**
   - Standardize on `owner=request.user` (and set `added_by=request.user` on creation), filter `is_bookmarked` by `owner`, allow `owner=request.user` in `bookmark_view`/`bookmark_delete` for superadmins, and map per-model URL kwargs (`video_id`, `hine_id`, `da_id`, `cdic_id`, `gpa_id`) in [`Bookmark.get_bookmarked_object_url()`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/patients/models.py#L2374-L2395).
3. **Fix ReportLab XML Escaping & Export Field Mismatches:**
   - Escape user strings with `xml.sax.saxutils.escape()` before passing to `Paragraph()` in [`reports/utils/pdf_generator.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/utils/pdf_generator.py).
   - Add `hsl_*` and `seb_*` domains to [`pdf_generator.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/utils/pdf_generator.py#L526-L561) and [`excel_generator.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/utils/excel_generator.py#L524-L529), and fix field names in [`referral/utils.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/referral/utils.py#L84-L95).
4. **Fix CSP Nonces & Inline Event Handlers:**
   - Add `nonce="{{ request.csp_nonce }}"` to `<script>` tags in [`superadmin_patient_move.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/institution/superadmin_patient_move.html#L206), [`backup/create.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/backup/templates/backup/create.html#L118), [`reports/history.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/reports/templates/reports/history.html#L135), and [`patients/search.html`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/patients/search.html#L51), and replace inline `onclick=`/`onchange=` handlers with `addEventListener`.

### Phase 3 — Performance & UX Polish
1. **Eliminate N+1 Queries:** Add `@cached_property` (or prefetch) for `Patient.getDiagnosisList`, pass `user=request.user` in `patient_manager`, and chain `.with_assessment_status().with_bookmark_status(request.user)` in `video_manager*`.
2. **Remove Blocking Geolocation Calls on Login:** Cache IP lookups in Django cache and reduce timeout or move off the synchronous login path in [`users/utils.py`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/users/utils.py#L69-L104).
3. **Fix Notification Dropdown & Script Ordering:** Change `hx-trigger` in [`navbar.html:123`](file:///d:/Projects/Current%20Projects/NDAS%20-%20Project/NDAS/templates/src/navbar.html#L123) to `click from:closest .nav-item once`, and move inline jQuery scripts from `{% block main_content %}` to `{% block extra_js %}`.
