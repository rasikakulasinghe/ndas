import sys
import os
import time
import json
import traceback
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8000"
UPLOAD_DIR = r"d:\Projects\Current Projects\NDAS - Project\NDAS\Files for test uploads"

# Test Files
VIDEO_FILE = os.path.join(UPLOAD_DIR, "video test.mp4")
PDF_FILE = os.path.join(UPLOAD_DIR, "pdf test.pdf")
IMAGE_FILE = os.path.join(UPLOAD_DIR, "image test.png")

# Test Logs
logs = []
screenshots_dir = "qa_screenshots"
os.makedirs(screenshots_dir, exist_ok=True)

def log_step(name, status, details="", traceback_str=""):
    log_entry = {
        "step": name,
        "status": status,
        "details": details,
        "traceback": traceback_str,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    logs.append(log_entry)
    print(f"[{status}] {name}: {details}")
    if traceback_str:
        print(traceback_str)

def run_tests():
    with sync_playwright() as p:
        # Launch Chromium headless
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Listen for console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        # Listen for page crashes/errors
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(err.message))

        try:
            # --- 1. Login ---
            log_step("Navigate to Login", "INFO", "Going to login page")
            page.goto(f"{BASE_URL}/users/login/")
            page.screenshot(path=f"{screenshots_dir}/1_login_page.png")
            
            page.fill("input[name='username']", "testadmin")
            page.fill("input[name='password']", "TestAdminPass123!")
            page.screenshot(path=f"{screenshots_dir}/2_login_filled.png")
            
            page.click("button[type='submit']")
            page.wait_for_timeout(2000)
            
            if "login" in page.url:
                raise Exception(f"Login failed! Current URL: {page.url}")
            
            log_step("Login", "SUCCESS", f"Logged in successfully. URL: {page.url}")
            page.screenshot(path=f"{screenshots_dir}/3_dashboard.png")

            # --- 2. User CRUD (Create, Read, Update, Delete) ---
            log_step("User Admin List", "INFO", "Going to admin user list page")
            page.goto(f"{BASE_URL}/users/admin/users/")
            page.screenshot(path=f"{screenshots_dir}/2_1_user_list.png")

            log_step("Navigate to Add User", "INFO", "Going to admin user add page")
            page.goto(f"{BASE_URL}/users/admin/users/add/")
            page.screenshot(path=f"{screenshots_dir}/2_2_add_user_form.png")

            test_username = f"qa_user_{int(time.time())}"
            page.fill("input[name='username']", test_username)
            page.fill("input[name='first_name']", "QAFirst")
            page.fill("input[name='last_name']", "QALast")
            page.fill("input[name='email']", f"{test_username}@example.com")
            page.select_option("select[name='position']", "Medical Officer")
            page.fill("input[name='mobile_primary']", "+94712345679")
            page.fill("input[name='password1']", "QaTestPass123!")
            page.fill("input[name='password2']", "QaTestPass123!")
            page.screenshot(path=f"{screenshots_dir}/2_3_add_user_filled.png")
            
            page.click("button[type='submit']")
            page.wait_for_url("**/admin/users/", wait_until="domcontentloaded", timeout=20000)

            # Check redirection back to user list
            if "admin/users/" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"User creation failed! URL: {page.url}. Form errors: {err_text}")
            
            log_step("Create User", "SUCCESS", f"User '{test_username}' created successfully.")
            page.screenshot(path=f"{screenshots_dir}/2_4_user_list_after_create.png")

            # Let's find the created user in the table and edit it
            user_row = page.locator(f"tr:has-text('{test_username}')")
            edit_link = user_row.locator("a[href*='/edit/']")
            if not edit_link.count():
                raise Exception(f"Could not find edit button for user '{test_username}' in table")
            
            edit_url = edit_link.first.get_attribute("href")
            created_user_id = edit_url.split("admin/users/")[1].split("/edit")[0]
            log_step("Read User", "SUCCESS", f"User ID read from table: {created_user_id}. Edit URL: {edit_url}")

            log_step("Navigate to Edit User", "INFO", f"Editing user {created_user_id}")
            page.goto(f"{BASE_URL}{edit_url}")
            page.screenshot(path=f"{screenshots_dir}/2_5_edit_user_form.png")
            page.fill("input[name='first_name']", "QAFirstUpdated")
            page.click("button[type='submit']")
            page.wait_for_url("**/admin/users/", wait_until="domcontentloaded", timeout=20000)
            log_step("Update User", "SUCCESS", f"User {created_user_id} updated. Redirection URL: {page.url}")

            # Deactivate (Delete) user using modal
            log_step("Delete (Deactivate) User", "INFO", f"Deactivating user {created_user_id}")
            # Find delete trigger button in the row for our user
            page.goto(f"{BASE_URL}/users/admin/users/")
            user_row = page.locator(f"tr:has-text('{test_username}')")
            delete_trigger = user_row.locator(".delete-trigger-btn")
            if not delete_trigger.count():
                raise Exception("Could not find delete button trigger for user")
            
            modal_target = delete_trigger.first.get_attribute("data-modal-target")
            log_step("Triggering Delete Modal", "INFO", f"Modal target: {modal_target}")
            delete_trigger.first.click()
            page.wait_for_selector(f"#{modal_target}", state="visible")
            
            # Fill password
            page.fill(f"#deletePassword{modal_target}", "TestAdminPass123!")
            page.screenshot(path=f"{screenshots_dir}/2_6_delete_user_modal.png")
            with page.expect_navigation(url="**/admin/users/", wait_until="load", timeout=25000):
                page.locator(f"#{modal_target} button.delete-confirm-btn").click()
            log_step("Delete User", "SUCCESS", f"User {test_username} soft-deleted/deactivated.")

            # --- 3. Patient CRUD (Create, Read, Update) ---
            log_step("Navigate to Add Patient", "INFO", "Going to patient add page")
            page.goto(f"{BASE_URL}/patient/add/")
            
            patient_bht = f"QA-BHT-{int(time.time())}"
            page.fill("input[name='bht']", patient_bht)
            page.fill("input[name='nnc_no']", f"QA-NNC-{int(time.time())}")
            page.fill("input[name='baby_name']", "QA Test Baby")
            page.fill("input[name='mother_name']", "QA Test Mother")
            page.select_option("select[name='gender']", "Male")
            page.fill("input[name='dob_tob']", "2026-06-01T12:00")
            page.select_option("select[name='pog_wks']", "39")
            page.select_option("select[name='pog_days']", "3")
            page.select_option("select[name='mo_delivery']", "Normal vaginal delivery (NVD)")
            page.fill("input[name='birth_weight']", "3200")
            page.fill("input[name='ofc']", "34")
            page.fill("input[name='tp_mobile']", "+94712345678")
            
            page.screenshot(path=f"{screenshots_dir}/3_1_add_patient_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/patient/view/**", wait_until="domcontentloaded", timeout=20000)

            if "patient/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"Patient creation failed! URL: {page.url}. Form errors: {err_text}")
            
            patient_url = page.url
            patient_id = patient_url.split("patient/view/")[1].split("/")[0]
            log_step("Create Patient", "SUCCESS", f"Patient created. ID: {patient_id}. URL: {patient_url}")

            # Update patient
            log_step("Navigate to Edit Patient", "INFO", f"Editing patient {patient_id}")
            page.goto(f"{BASE_URL}/patient/edit/{patient_id}/")
            page.fill("input[name='baby_name']", "QA Test Baby Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/manager/patient/", wait_until="domcontentloaded", timeout=20000)
            log_step("Update Patient", "SUCCESS", f"Patient updated. URL: {page.url}")

            # Go back to patient view
            page.goto(f"{BASE_URL}/patient/view/{patient_id}/")
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{screenshots_dir}/3_2_patient_view.png")

            # --- 4. Problem CRUD (Create, Read, Update, Delete) ---
            log_step("Navigate to Add Problem", "INFO", f"Adding problem to patient {patient_id}")
            page.goto(f"{BASE_URL}/problems/add/{patient_id}/")
            page.screenshot(path=f"{screenshots_dir}/4_1_add_problem_form.png")

            page.fill("input[name='name']", "QA Problem Asthma")
            page.fill("textarea[name='description']", "QA problem description bronchial asthma")
            page.fill("input[name='date_of_onset']", "2026-06-02")
            page.fill("input[name='date_identified']", "2026-06-02")
            page.select_option("select[name='status']", "active")
            page.select_option("select[name='severity']", "moderate")
            page.fill("textarea[name='action_taken']", "QA action details")
            page.fill("textarea[name='outcome']", "QA outcome details")
            page.screenshot(path=f"{screenshots_dir}/4_2_add_problem_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/problems/manager/**", wait_until="domcontentloaded", timeout=20000)

            log_step("Create Problem", "SUCCESS", f"Problem created. Redirection URL: {page.url}")
            page.screenshot(path=f"{screenshots_dir}/4_3_after_problem_create.png")

            # Find edit problem link
            edit_problem_link = page.locator("a[href*='/problems/edit/']")
            if not edit_problem_link.count():
                page.goto(f"{BASE_URL}/patient/view/{patient_id}/")
                page.wait_for_timeout(1000)
                edit_problem_link = page.locator("a[href*='/problems/edit/']")
            
            if not edit_problem_link.count():
                raise Exception("Could not find edit link for Problem")
            
            problem_edit_url = edit_problem_link.first.get_attribute("href")
            problem_id = problem_edit_url.split("/problems/edit/")[1].split("/")[0]
            log_step("Read Problem", "SUCCESS", f"Problem ID read: {problem_id}. Edit URL: {problem_edit_url}")

            # Edit Problem
            log_step("Navigate to Edit Problem", "INFO", f"Editing problem {problem_id}")
            page.goto(f"{BASE_URL}{problem_edit_url}")
            page.screenshot(path=f"{screenshots_dir}/4_4_edit_problem_form.png")
            page.fill("input[name='name']", "QA Problem Asthma Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/problems/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update Problem", "SUCCESS", f"Problem updated. Redirect URL: {page.url}")

            # Add Problem Action
            log_step("Navigate to Add Problem Action", "INFO", f"Adding action to problem {problem_id}")
            page.goto(f"{BASE_URL}/problems/action/add/{problem_id}/")
            page.screenshot(path=f"{screenshots_dir}/4_5_problem_action_form.png")
            page.fill("textarea[name='action']", "QA new action entry logs.")
            page.click("button[type='submit']")
            page.wait_for_url("**/problems/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Add Problem Action", "SUCCESS", f"Action logged. URL: {page.url}")

            # --- 5. Video CRUD (Create, Read, Update) ---
            log_step("Navigate to Upload Video", "INFO", f"Uploading video for patient {patient_id}")
            page.goto(f"{BASE_URL}/video/add/{patient_id}/")
            page.fill("input[name='title']", "QA Test Video")
            page.fill("textarea[name='description']", "QA test video upload description")
            page.set_input_files("input[type='file']", VIDEO_FILE)
            page.screenshot(path=f"{screenshots_dir}/5_1_video_upload_filled.png")
            
            page.click("button[type='submit']")
            page.wait_for_url("**/video/view/**", wait_until="domcontentloaded", timeout=60000)

            if "video/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"Video upload failed! URL: {page.url}. Form errors: {err_text}")

            video_url = page.url
            video_id = video_url.split("video/view/")[1].split("/")[0]
            log_step("Create Video", "SUCCESS", f"Video uploaded. ID: {video_id}. URL: {video_url}")

            # Update Video
            log_step("Navigate to Edit Video", "INFO", f"Editing video {video_id}")
            page.goto(f"{BASE_URL}/video/edit/{video_id}/")
            page.fill("input[name='title']", "QA Test Video Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/video/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update Video", "SUCCESS", f"Video updated. URL: {page.url}")

            # --- 6. GMAssessment CRUD (Create, Read, Update) ---
            log_step("Navigate to Add GMAssessment", "INFO", f"Adding GM assessment for patient {patient_id}, video {video_id}")
            page.goto(f"{BASE_URL}/assessment/add/{patient_id}/{video_id}/")
            page.screenshot(path=f"{screenshots_dir}/6_1_gma_form.png")

            page.fill("input[name='date_of_assessment']", "2026-06-03T10:00")
            page.click("div[data-target='#diagnosisCard']")
            page.wait_for_timeout(500)
            page.locator("label:has-text('Normal (Normal)') input[type='checkbox']").check()
            page.select_option("select[name='diagnosis_conclusion']", "NORMAL")
            page.fill("textarea[name='management_plan']", "QA GM Assessment management plan details")
            page.check("input[name='parent_informed']")
            page.screenshot(path=f"{screenshots_dir}/6_2_gma_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/assessment/view/**", wait_until="domcontentloaded", timeout=20000)

            if "assessment/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"GMAssessment creation failed! URL: {page.url}. Form errors: {err_text}")

            gma_url = page.url
            gma_id = gma_url.split("assessment/view/")[1].split("/")[0]
            log_step("Create GMAssessment", "SUCCESS", f"GMAssessment created. ID: {gma_id}. URL: {gma_url}")

            # Edit GMAssessment
            log_step("Navigate to Edit GMAssessment", "INFO", f"Editing GMAssessment {gma_id}")
            page.goto(f"{BASE_URL}/assessment/edit/{gma_id}/")
            page.fill("textarea[name='management_plan']", "QA GM Assessment management plan details Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/assessment/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update GMAssessment", "SUCCESS", f"GMAssessment updated. URL: {page.url}")

            # --- 7. HINEAssessment CRUD (Create, Read, Update) ---
            log_step("Navigate to Add HINEAssessment", "INFO", f"Adding HINE assessment for patient {patient_id}")
            page.goto(f"{BASE_URL}/hine/add/{patient_id}/")
            page.fill("input[name='date_of_assessment']", "2026-06-03T10:00")
            page.fill("input[name='score']", "74")
            page.fill("input[name='assessment_done_by']", "QA Doctor")
            page.fill("textarea[name='comment']", "QA HINE Comment details")
            page.screenshot(path=f"{screenshots_dir}/7_1_hine_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/hine/view/**", wait_until="domcontentloaded", timeout=20000)

            if "hine/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"HINEAssessment creation failed! URL: {page.url}. Form errors: {err_text}")

            hine_url = page.url
            hine_id = hine_url.split("hine/view/")[1].split("/")[0]
            log_step("Create HINEAssessment", "SUCCESS", f"HINEAssessment created. ID: {hine_id}. URL: {hine_url}")

            # Edit HINEAssessment
            log_step("Navigate to Edit HINEAssessment", "INFO", f"Editing HINEAssessment {hine_id}")
            page.goto(f"{BASE_URL}/hine/edit/{hine_id}/")
            page.fill("input[name='score']", "75")
            page.click("button[type='submit']")
            page.wait_for_url("**/hine/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update HINEAssessment", "SUCCESS", f"HINEAssessment updated. URL: {page.url}")

            # --- 8. DevelopmentalAssessment CRUD (Create, Read, Update) ---
            log_step("Navigate to Add DevelopmentalAssessment", "INFO", f"Adding DA assessment for patient {patient_id}")
            page.goto(f"{BASE_URL}/da/add/{patient_id}/")
            page.fill("input[name='date_of_assessment']", "2026-06-03T10:00")
            page.fill("input[name='gm_age_from']", "12")
            page.fill("input[name='gm_age_to']", "14")
            page.fill("textarea[name='gm_details']", "QA GM details")
            page.fill("input[name='assessment_done_by']", "QA Officer")
            page.screenshot(path=f"{screenshots_dir}/8_1_da_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/da/view/**", wait_until="domcontentloaded", timeout=20000)

            if "da/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"DevelopmentalAssessment creation failed! URL: {page.url}. Form errors: {err_text}")

            da_url = page.url
            da_id = da_url.split("da/view/")[1].split("/")[0]
            log_step("Create DevelopmentalAssessment", "SUCCESS", f"DA Assessment created. ID: {da_id}. URL: {da_url}")

            # Edit DA Assessment
            log_step("Navigate to Edit DevelopmentalAssessment", "INFO", f"Editing DA assessment {da_id}")
            page.goto(f"{BASE_URL}/da/edit/{da_id}/")
            page.fill("textarea[name='gm_details']", "QA GM details Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/da/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update DevelopmentalAssessment", "SUCCESS", f"DA Assessment updated. URL: {page.url}")

            # --- 9. GeneralPaediatricAssessment (GPA) CRUD (Create, Read, Update) ---
            log_step("Navigate to Add GPA", "INFO", f"Adding GPA assessment for patient {patient_id}")
            page.goto(f"{BASE_URL}/gpa/add/{patient_id}/")
            page.fill("input[name='assessment_date']", "2026-06-03T10:00")
            page.fill("input[name='healthcare_provider']", "QA Paediatrician")
            page.fill("textarea[name='current_problems']", "QA GPA Problems details")
            page.fill("textarea[name='physical_examination']", "QA GPA Exam details")
            page.fill("textarea[name='investigation_summary']", "QA GPA Investigation summary")
            page.fill("textarea[name='prescribed_medications']", "QA GPA Prescribed medications")
            page.fill("textarea[name='next_plan']", "QA GPA Next plan details")
            page.screenshot(path=f"{screenshots_dir}/9_1_gpa_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/patient/view/**", wait_until="domcontentloaded", timeout=20000)

            if "patient/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"GPA creation failed! URL: {page.url}. Form errors: {err_text}")

            # Click the GPA tab to reveal the GPA table
            page.locator("#gpa-tab").click()
            page.wait_for_timeout(500)
            
            # Find the view or edit link for the GPA record we just created
            gpa_link = page.locator("a[href*='/gpa/view/']")
            if not gpa_link.count():
                gpa_link = page.locator("a[href*='/gpa/edit/']")
                
            if not gpa_link.count():
                raise Exception("Could not find view/edit link for GPA on patient view page")
                
            gpa_edit_url = gpa_link.first.get_attribute("href")
            if "gpa/view/" in gpa_edit_url:
                gpa_id = gpa_edit_url.split("gpa/view/")[1].split("/")[0]
            else:
                gpa_id = gpa_edit_url.split("gpa/edit/")[1].split("/")[0]
                
            gpa_url = f"{BASE_URL}/gpa/view/{gpa_id}/"
            log_step("Create GPA", "SUCCESS", f"GPA created. ID: {gpa_id}. URL: {gpa_url}")

            # Edit GPA
            log_step("Navigate to Edit GPA", "INFO", f"Editing GPA {gpa_id}")
            page.goto(f"{BASE_URL}/gpa/edit/{gpa_id}/")
            page.fill("textarea[name='current_problems']", "QA GPA Problems details Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/gpa/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update GPA", "SUCCESS", f"GPA updated. URL: {page.url}")

            # --- 10. CDIC Record CRUD (Create, Read, Update) ---
            log_step("Navigate to Add CDICRecord", "INFO", f"Adding CDIC assessment for patient {patient_id}")
            page.goto(f"{BASE_URL}/cdic/add/{patient_id}/")
            page.fill("input[name='assessment_date']", "2026-06-03")
            page.fill("textarea[name='assessment']", "QA CDIC Assessment details")
            page.fill("input[name='assessment_done_by']", "QA Special Officer")
            page.screenshot(path=f"{screenshots_dir}/10_1_cdic_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/cdic/view/**", wait_until="domcontentloaded", timeout=20000)

            if "cdic/view" not in page.url:
                err_text = page.locator(".invalid-feedback, .alert-danger").all_text_contents()
                raise Exception(f"CDIC creation failed! URL: {page.url}. Form errors: {err_text}")

            cdic_url = page.url
            cdic_id = cdic_url.split("cdic/view/")[1].split("/")[0]
            log_step("Create CDICRecord", "SUCCESS", f"CDIC created. ID: {cdic_id}. URL: {cdic_url}")

            # Edit CDIC
            log_step("Navigate to Edit CDICRecord", "INFO", f"Editing CDICRecord {cdic_id}")
            page.goto(f"{BASE_URL}/cdic/edit/{cdic_id}/")
            page.fill("textarea[name='assessment']", "QA CDIC Assessment details Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/cdic/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update CDICRecord", "SUCCESS", f"CDICRecord updated. URL: {page.url}")

            # --- 11. Attachment CRUD (Create, Read, Update) ---
            log_step("Navigate to Add Attachment", "INFO", f"Adding attachment for patient {patient_id}")
            page.goto(f"{BASE_URL}/attachment/add/{patient_id}/")
            page.fill("input[name='title']", "QA Test Attachment")
            page.fill("textarea[name='description']", "QA test description for pdf document upload")
            page.set_input_files("input[type='file']", PDF_FILE)
            page.screenshot(path=f"{screenshots_dir}/11_1_attachment_filled.png")
            page.click("button[type='submit']")
            page.wait_for_url("**/attachment/view/**", wait_until="domcontentloaded", timeout=20000)

            attachment_id = page.url.split("/attachment/view/")[1].split("/")[0]
            attachment_edit_url = f"/attachment/edit/{attachment_id}/"
            log_step("Create Attachment", "SUCCESS", f"Attachment uploaded. ID: {attachment_id}. Edit URL: {attachment_edit_url}")

            # Edit Attachment
            log_step("Navigate to Edit Attachment", "INFO", f"Editing attachment {attachment_id}")
            page.goto(f"{BASE_URL}{attachment_edit_url}")
            page.screenshot(path=f"{screenshots_dir}/11_2_edit_attachment_form.png")
            page.fill("input[name='title']", "QA Test Attachment Updated")
            page.click("button[type='submit']")
            page.wait_for_url("**/attachment/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Update Attachment", "SUCCESS", f"Attachment updated. URL: {page.url}")

            # --- 12. Bookmark CRUD (Create, Delete) ---
            log_step("Add Bookmark", "INFO", f"Bookmarking patient {patient_id}")
            page.goto(f"{BASE_URL}/bookmarks/add/{patient_id}/Patient/")
            page.screenshot(path=f"{screenshots_dir}/12_1_add_bookmark_form.png")
            page.fill("input[name='title']", "QA Patient Bookmark")
            page.fill("textarea[name='description']", "QA Patient Bookmark Description")
            page.click("button[type='submit']")
            page.wait_for_url("**/bookmarks/view/**", wait_until="domcontentloaded", timeout=20000)
            log_step("Create Bookmark", "SUCCESS", f"Bookmark created. URL: {page.url}")

            # Find bookmark ID from bookmarks list
            page.goto(f"{BASE_URL}/manager/bookmarks/")
            page.screenshot(path=f"{screenshots_dir}/12_2_bookmark_manager.png")
            # Open the actions dropdown for our bookmark row first to expose the delete button
            bookmark_row = page.locator("tr:has-text('QA Patient Bookmark')").first
            bookmark_delete_btn = bookmark_row.locator(".delete-trigger-btn")
            if not bookmark_delete_btn.count():
                raise Exception("Could not find delete button trigger for Bookmark in the row")
            
            bookmark_modal_id = bookmark_delete_btn.get_attribute("data-modal-target")
            bookmark_id = bookmark_modal_id.replace("deleteBookmarkModal", "")
            log_step("Read Bookmark", "SUCCESS", f"Bookmark ID: {bookmark_id}. Modal: {bookmark_modal_id}")

            # Delete Bookmark using modal
            log_step("Delete Bookmark", "INFO", f"Deleting bookmark {bookmark_id}")
            bookmark_row.locator("button[data-toggle='dropdown']").click()
            page.wait_for_timeout(500)
            bookmark_delete_btn.click()
            page.wait_for_selector(f"#{bookmark_modal_id}", state="visible")
            page.fill(f"#deletePassword{bookmark_modal_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/manager/bookmarks/**", wait_until="load", timeout=25000):
                page.locator(f"#{bookmark_modal_id} button.delete-confirm-btn").click()
            log_step("Delete Bookmark", "SUCCESS", "Bookmark deleted.")

            # Go back to patient details page
            page.goto(f"{BASE_URL}/patient/view/{patient_id}/")
            page.wait_for_timeout(1000)
            page.screenshot(path=f"{screenshots_dir}/13_patient_view_before_deletes.png")

            # --- 13. Delete Assessments ---
            # Delete Problem
            log_step("Delete Problem", "INFO", f"Deleting problem {problem_id}")
            page.goto(f"{BASE_URL}/problems/manager/{patient_id}/")
            page.wait_for_timeout(1000)
            problem_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteProblemModal{problem_id}']")
            if not problem_delete_btn.count():
                raise Exception(f"Problem delete trigger not found for id {problem_id}")
            problem_delete_btn.click()
            page.wait_for_selector(f"#deleteProblemModal{problem_id}", state="visible")
            page.fill(f"#deletePassworddeleteProblemModal{problem_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/problems/manager/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteProblemModal{problem_id} button.delete-confirm-btn").click()
            log_step("Delete Problem", "SUCCESS", "Problem deleted.")

            # Go back to patient details page for other deletes
            page.goto(f"{BASE_URL}/patient/view/{patient_id}/")
            page.wait_for_timeout(1000)

            # Delete GMAssessment
            log_step("Delete GMAssessment", "INFO", f"Deleting GMAssessment {gma_id}")
            page.locator("#gm-tab").click()
            page.wait_for_timeout(500)
            gma_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteGMAssessmentModal{gma_id}']")
            gma_delete_btn.click()
            page.wait_for_selector(f"#deleteGMAssessmentModal{gma_id}", state="visible")
            page.fill(f"#deletePassworddeleteGMAssessmentModal{gma_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/patient/view/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteGMAssessmentModal{gma_id} button.delete-confirm-btn").click()
            log_step("Delete GMAssessment", "SUCCESS", "GMAssessment deleted.")

            # Delete HINEAssessment
            log_step("Delete HINEAssessment", "INFO", f"Deleting HINEAssessment {hine_id}")
            page.locator("#hine-tab").click()
            page.wait_for_timeout(500)
            hine_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteHINEAssessmentModal{hine_id}']")
            hine_delete_btn.click()
            page.wait_for_selector(f"#deleteHINEAssessmentModal{hine_id}", state="visible")
            page.fill(f"#deletePassworddeleteHINEAssessmentModal{hine_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/patient/view/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteHINEAssessmentModal{hine_id} button.delete-confirm-btn").click()
            log_step("Delete HINEAssessment", "SUCCESS", "HINEAssessment deleted.")

            # Delete DevelopmentalAssessment
            log_step("Delete DevelopmentalAssessment", "INFO", f"Deleting DevelopmentalAssessment {da_id}")
            page.locator("#da-tab").click()
            page.wait_for_timeout(500)
            da_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteDevelopmentalAssessmentModal{da_id}']")
            da_delete_btn.click()
            page.wait_for_selector(f"#deleteDevelopmentalAssessmentModal{da_id}", state="visible")
            page.fill(f"#deletePassworddeleteDevelopmentalAssessmentModal{da_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/patient/view/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteDevelopmentalAssessmentModal{da_id} button.delete-confirm-btn").click()
            log_step("Delete DevelopmentalAssessment", "SUCCESS", "DevelopmentalAssessment deleted.")

            # Delete GPA
            log_step("Delete GPA", "INFO", f"Deleting GPA {gpa_id}")
            page.locator("#gpa-tab").click()
            page.wait_for_timeout(500)
            gpa_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteGeneralPaediatricAssessmentModal{gpa_id}']")
            gpa_delete_btn.click()
            page.wait_for_selector(f"#deleteGeneralPaediatricAssessmentModal{gpa_id}", state="visible")
            page.fill(f"#deletePassworddeleteGeneralPaediatricAssessmentModal{gpa_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/patient/view/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteGeneralPaediatricAssessmentModal{gpa_id} button.delete-confirm-btn").click()
            log_step("Delete GPA", "SUCCESS", "GPA deleted.")

            # Delete CDICRecord
            log_step("Delete CDICRecord", "INFO", f"Deleting CDICRecord {cdic_id}")
            page.locator("#cdic-tab").click()
            page.wait_for_timeout(500)
            cdic_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteCDICRecordModal{cdic_id}']")
            cdic_delete_btn.click()
            page.wait_for_selector(f"#deleteCDICRecordModal{cdic_id}", state="visible")
            page.fill(f"#deletePassworddeleteCDICRecordModal{cdic_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/patient/view/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteCDICRecordModal{cdic_id} button.delete-confirm-btn").click()
            log_step("Delete CDICRecord", "SUCCESS", "CDICRecord deleted.")

            # Delete Attachment
            log_step("Delete Attachment", "INFO", f"Deleting Attachment {attachment_id}")
            page.locator("#attachments-tab").click()
            page.wait_for_timeout(500)
            attach_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteAttachmentModal{attachment_id}']")
            attach_delete_btn.click()
            page.wait_for_selector(f"#deleteAttachmentModal{attachment_id}", state="visible")
            page.fill(f"#deletePassworddeleteAttachmentModal{attachment_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/patient/view/**", wait_until="load", timeout=25000):
                page.locator(f"#deleteAttachmentModal{attachment_id} button.delete-confirm-btn").click()
            log_step("Delete Attachment", "SUCCESS", "Attachment deleted.")

            # Delete Video
            log_step("Delete Video", "INFO", f"Deleting Video {video_id}")
            page.locator("#videos-tab").click()
            page.wait_for_timeout(500)
            video_delete_btn = page.locator(f".delete-trigger-btn[data-modal-target='deleteVideoModal{video_id}']")
            video_delete_btn.click()
            page.wait_for_selector(f"#deleteVideoModal{video_id}", state="visible")
            page.fill(f"#deletePassworddeleteVideoModal{video_id}", "TestAdminPass123!")
            with page.expect_navigation(url="**/video/manager/", wait_until="load", timeout=25000):
                page.locator(f"#deleteVideoModal{video_id} button.delete-confirm-btn").click()
            log_step("Delete Video", "SUCCESS", "Video deleted.")

            # Go back to patient details page
            page.goto(f"{BASE_URL}/patient/view/{patient_id}/")
            page.wait_for_timeout(1000)

            # Delete Patient
            log_step("Delete Patient", "INFO", f"Deleting Patient {patient_id}")
            page.locator("button[data-modal-target='deletePatientModal']").click()
            page.wait_for_selector("#deletePatientModal", state="visible")
            page.fill("#deletePassworddeletePatientModal", "TestAdminPass123!")
            with page.expect_navigation(url="**/manager/patient/", wait_until="load", timeout=25000):
                page.locator("#deletePatientModal button.delete-confirm-btn").click()
            log_step("Delete Patient", "SUCCESS", "Patient deleted successfully.")

            page.screenshot(path=f"{screenshots_dir}/14_patient_list_after_deletes.png")
            log_step("Final Check", "SUCCESS", "All CRUD actions completed successfully!")

        except Exception as e:
            tb = traceback.format_exc()
            log_step("Execution Error", "FAILED", str(e), tb)
            page.screenshot(path=f"{screenshots_dir}/error_screenshot.png")
        finally:
            browser.close()

if __name__ == "__main__":
    run_tests()
    
    # Save test logs to file
    with open("qa_test_run_logs.json", "w") as f:
        json.dump(logs, f, indent=4)
