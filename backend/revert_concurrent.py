"""
Revert concurrent processing changes in fastapi_backend.py
This will restore the sequential processing while keeping other fixes
"""
import re

print("Reading fastapi_backend.py...")
with open('fastapi_backend.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the env_int function and CONCURRENT_BROWSERS definition
pattern1 = r'# Concurrent processing configuration.*?CONCURRENT_BROWSERS = env_int\("CONCURRENT_BROWSERS", 1\)\r?\n\r?\n'
content = re.sub(pattern1, '', content, flags=re.DOTALL)

# Revert Phase 1 scraping to sequential
phase1_concurrent = r'(# PHASE 1: SCRAPE.*?agg = \{[^}]+\}\s+)\s+# Process URLs in batches.*?update_run\(run_id, status="scraping".*?\)\s+'
phase1_sequential = r'''\1
        
        for idx, url in enumerate(planned_urls):
            if is_paused(campaign_id):
                update_run(run_id, status="paused", progress=scraped_count, total=planned_total)
                return
            
            one_userdata = {"websites": [url]}
            
            # Phase 1: Scrape only (mode="scrape") - discovers fields, no submit
            scrape_result = await scrapeallforms(one_userdata, 1)
            
            if isinstance(scrape_result, dict):
                details = scrape_result.get("details") or []
                if details:
                    scrape_results.append(details[0])
                    # Track results in real-time
                    detail_status = str(details[0].get("status") or "").lower()
                    if detail_status == "captcha":
                        agg["captcha"] += 1
                    elif detail_status == "noform":
                        agg["noform"] += 1
                    elif detail_status == "scraped":
                        agg["scraped"] += 1
            
            scraped_count += 1
            agg["total"] = scraped_count
            update_run(run_id, status="scraping", progress=scraped_count, total=planned_total, results=db_json(agg))
'''

content = re.sub(phase1_concurrent, phase1_sequential, content, flags=re.DOTALL)

# Revert Phase 2 filling to sequential  
phase2_concurrent = r'(# Phase 2: Fill and submit only URLs with discovered forms)\s+# Process in batches.*?update_run\(run_id, status="filling".*?\)\s+'
phase2_sequential = r'''\1
        for site_info in urls_with_forms:
            if is_paused(campaign_id):
                update_run(run_id, status="paused", progress=done, total=planned_total)
                return

            url = site_info["url"]
            one_userdata = dict(base_userdata)
            one_userdata["websites"] = [url]

            # Phase 2: Fill mode - actually submits forms
            results_one = await fillallforms(one_userdata, 1, mode="fill")

            if isinstance(results_one, dict):
                agg["total"] += int(results_one.get("total") or 0)
                agg["success"] += int(results_one.get("success") or 0)
                agg["failed"] += int(results_one.get("failed") or 0)
                agg["captcha"] += int(results_one.get("captcha") or 0)

            done += 1
            update_run(run_id, status="filling", progress=done, total=len(urls_with_forms), results=db_json(agg))
'''

content = re.sub(phase2_concurrent, phase2_sequential, content, flags=re.DOTALL)

# Write back
with open('fastapi_backend.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Reverted concurrent processing changes")
print("✅ Server should now start normally")
print("\nTo start server: python fastapi_backend.py")
