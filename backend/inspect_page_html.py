#!/usr/bin/env python3
"""
Simple script to check what HTML is actually on the contact page
This uses basic HTTP to fetch the page without a browser
"""

import requests
from bs4 import BeautifulSoup

url = "http://site23359-uw0p89.scloudsite101.com/service"

print(f"Fetching: {url}\n")

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    
    print(f"✓ Status: {response.status_code}")
    print(f"✓ Content-Type: {response.headers.get('content-type')}\n")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check for forms
    forms = soup.find_all('form')
    print(f"{'='*60}")
    print(f"FORMS FOUND: {len(forms)}")
    print(f"{'='*60}")
    
    if forms:
        for idx, form in enumerate(forms, 1):
            print(f"\n--- Form {idx} ---")
            print(f"Action: {form.get('action', 'N/A')}")
            print(f"Method: {form.get('method', 'N/A')}")
            print(f"ID: {form.get('id', 'N/A')}")
            print(f"Class: {form.get('class', 'N/A')}")
            
            # Count fields in this form
            inputs = form.find_all('input')
            textareas = form.find_all('textarea')
            selects = form.find_all('select')
            
            print(f"  Inputs: {len(inputs)}")
            print(f"  Textareas: {len(textareas)}")
            print(f"  Selects: {len(selects)}")
            
            # Show input details
            if inputs:
                print(f"\n  Input Fields:")
                for inp in inputs:
                    inp_type = inp.get('type', 'text')
                    inp_name = inp.get('name', 'N/A')
                    inp_id = inp.get('id', 'N/A')
                    inp_placeholder = inp.get('placeholder', 'N/A')
                    print(f"    - Type: {inp_type}, Name: {inp_name}, ID: {inp_id}, Placeholder: {inp_placeholder}")
            
            if textareas:
                print(f"\n  Textarea Fields:")
                for ta in textareas:
                    ta_name = ta.get('name', 'N/A')
                    ta_id = ta.get('id', 'N/A')
                    ta_placeholder = ta.get('placeholder', 'N/A')
                    print(f"    - Name: {ta_name}, ID: {ta_id}, Placeholder: {ta_placeholder}")
    else:
        print("\n❌ No <form> tags found in HTML")
    
    # Check for all inputs regardless of forms
    print(f"\n{'='*60}")
    print(f"ALL INPUTS (outside forms)")
    print(f"{'='*60}")
    
    all_inputs = soup.find_all('input')
    all_textareas = soup.find_all('textarea')
    all_selects = soup.find_all('select')
    
    print(f"Total inputs: {len(all_inputs)}")
    print(f"Total textareas: {len(all_textareas)}")
    print(f"Total selects: {len(all_selects)}")
    
    # Check for iframes
    print(f"\n{'='*60}")
    print(f"IFRAMES")
    print(f"{'='*60}")
    
    iframes = soup.find_all('iframe')
    print(f"Total iframes: {len(iframes)}")
    
    if iframes:
        for idx, iframe in enumerate(iframes, 1):
            print(f"\n--- Iframe {idx} ---")
            print(f"Src: {iframe.get('src', 'N/A')}")
            print(f"ID: {iframe.get('id', 'N/A')}")
            print(f"Name: {iframe.get('name', 'N/A')}")
    
    # Show a snippet of the HTML
    print(f"\n{'='*60}")
    print(f"HTML SNIPPET (first 2000 chars)")
    print(f"{'='*60}")
    print(response.text[:2000])
    
    # Check for common form builder scripts
    print(f"\n{'='*60}")
    print(f"JAVASCRIPT FORM BUILDERS DETECTED")
    print(f"{'='*60}")
    
    scripts = soup.find_all('script', src=True)
    form_builders = []
    
    for script in scripts:
        src = script.get('src', '').lower()
        if any(keyword in src for keyword in ['typeform', 'jotform', 'wufoo', 'formstack', 'gravity', 'contact-form', 'form-builder']):
            form_builders.append(script.get('src'))
    
    if form_builders:
        print("Found potential form builder scripts:")
        for fb in form_builders:
            print(f"  - {fb}")
    else:
        print("No common form builder scripts detected")
    
    print(f"\n{'='*60}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*60}")
    
except requests.RequestException as e:
    print(f"❌ Error fetching page: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
