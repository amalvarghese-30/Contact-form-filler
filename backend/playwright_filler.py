# FILE #3: backend/playwright_filler.py
# Browser Automation Engine - Copy this EXACTLY

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import random

logger = logging.getLogger(__name__)


class PlaywrightFormFiller:
    """Playwright-based form automation engine"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser = None
        self.playwright = None
    
    async def initialize(self):
        """Initialize Playwright browser"""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=self.headless)
            logger.info("Playwright browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    async def close(self):
        """Close browser and cleanup"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Playwright browser closed")
    
    async def find_contact_page(self, base_url: str, timeout: int = 10000) -> Tuple[Optional[str], Optional[str]]:
        """Find contact page by trying common paths"""
        page = await self.browser.new_page()
        
        contact_paths = [
            '/contact', '/contact-us', '/contact_us', '/contactus',
            '/support', '/support-us', '/get-in-touch', '/reach-us',
            '/inquiry', '/inquiries', '/feedback', '/message-us',
        ]
        
        for path in contact_paths:
            contact_url = f"{base_url.rstrip('/')}{path}"
            try:
                logger.info(f"Trying: {contact_url}")
                response = await page.goto(contact_url, wait_until='networkidle', timeout=timeout)
                
                if response and response.status < 400:
                    # Check if form exists
                    form_exists = await page.query_selector('form')
                    if form_exists:
                        html = await page.content()
                        await page.close()
                        return contact_url, html
                
            except Exception as e:
                logger.debug(f"Failed to access {contact_url}: {str(e)}")
                continue
        
        await page.close()
        return None, None
    
    async def detect_captcha(self, page) -> bool:
        """Detect if CAPTCHA is present on page"""
        html = await page.content()
        html_lower = html.lower()
        
        captcha_indicators = [
            'recaptcha', 'g-recaptcha', 'hcaptcha', 'captcha',
            'bot-check', 'arkose', 'turnstile', 'cloudflare-challenge',
            'i_am_not_a_robot',
        ]
        
        for indicator in captcha_indicators:
            if indicator in html_lower:
                logger.warning(f"CAPTCHA detected: {indicator}")
                return True
        
        return False
    
    async def extract_form_fields(self, page) -> List[Dict]:
        """Extract all form fields with details"""
        fields = []
        
        try:
            # Get all input fields
            inputs = await page.query_selector_all('form input, form textarea, form select')
            
            for element in inputs:
                try:
                    name = await element.get_attribute('name')
                    field_type = await element.get_attribute('type') or 'text'
                    placeholder = await element.get_attribute('placeholder') or ''
                    required = await element.get_attribute('required')
                    
                    # Skip unwanted fields
                    if not name or field_type in ['hidden', 'submit', 'button']:
                        continue
                    
                    if any(x in name.lower() for x in ['captcha', 'recaptcha', 'token']):
                        continue
                    
                    field = {
                        'name': name,
                        'type': field_type,
                        'placeholder': placeholder,
                        'required': required is not None,
                    }
                    fields.append(field)
                    logger.info(f"Detected field: {name} ({field_type})")
                    
                except Exception as e:
                    logger.debug(f"Error extracting field: {str(e)}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in extract_form_fields: {e}")
        
        return fields
    
    def normalize_field_name(self, name: str) -> str:
        """Normalize field name to match our mapping"""
        name = name.lower().strip().replace(' ', '_').replace('-', '_')
        
        mappings = {
            'first_name': ['fname', 'first_name', 'firstname', 'given_name'],
            'last_name': ['lname', 'last_name', 'lastname', 'surname'],
            'email': ['email', 'email_address', 'e_mail', 'mail'],
            'phone': ['phone', 'phonenumber', 'telephone', 'mobile'],
            'company': ['company', 'organization', 'employer'],
            'message': ['message', 'comment', 'description', 'details', 'inquiry'],
            'subject': ['subject', 'topic', 'title', 'issue_type'],
            'address': ['address', 'street', 'location'],
            'city': ['city', 'town'],
            'state': ['state', 'province'],
            'zip': ['zip', 'postal_code', 'postcode'],
            'website': ['website', 'url', 'web'],
        }
        
        for standard, variants in mappings.items():
            for variant in variants:
                if variant in name:
                    return standard
        
        return name
    
    def generate_field_value(self, field_name: str, field_type: str) -> str:
        """Generate realistic value based on field name and type"""
        
        normalized = self.normalize_field_name(field_name)
        
        # Data pools for generation
        first_names = ['John', 'Sarah', 'Michael', 'Emma', 'David', 'Lisa', 'James', 'Maria']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Garcia', 'Miller', 'Davis']
        companies = ['Tech Solutions', 'Digital Ventures', 'Innovation Labs', 'Creative Agency']
        cities = ['New York', 'San Francisco', 'Chicago', 'Boston', 'Seattle', 'Austin']
        messages = [
            'I am interested in learning more about your services.',
            'I would like to schedule a meeting with your team.',
            'Could you provide information about your offerings?',
            'I have a question regarding your services.',
            'I would like to explore partnership opportunities.',
        ]
        
        if 'first' in normalized or (normalized == 'name' and 'first' in field_name.lower()):
            return random.choice(first_names)
        elif 'last' in normalized or 'surname' in normalized:
            return random.choice(last_names)
        elif normalized == 'email':
            first = random.choice(first_names).lower()
            return f"{first}.{random.randint(100,999)}@tempmail.com"
        elif normalized == 'phone':
            return f"+1{random.randint(200,999)}{random.randint(200,999)}{random.randint(1000,9999)}"
        elif normalized == 'company':
            return random.choice(companies)
        elif normalized == 'website':
            return f"https://www.business{random.randint(100,999)}.com"
        elif normalized == 'city':
            return random.choice(cities)
        elif normalized in ['message', 'description', 'details', 'comment']:
            return random.choice(messages)
        elif normalized in ['subject', 'title', 'topic']:
            return "General Inquiry"
        elif normalized == 'address':
            return f"{random.randint(100, 9999)} Business Street"
        elif normalized == 'state':
            return random.choice(['CA', 'NY', 'TX', 'FL', 'IL', 'PA', 'OH', 'GA'])
        elif normalized == 'zip':
            return f"{random.randint(10000, 99999)}"
        elif field_type == 'email':
            return f"user{random.randint(1000,9999)}@tempmail.com"
        elif field_type == 'tel':
            return f"+1{random.randint(2,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(1000,9999)}{random.randint(1000,9999)}"
        elif field_type in ['date', 'datetime-local']:
            future_date = datetime.now() + timedelta(days=random.randint(7, 30))
            return future_date.strftime("%Y-%m-%d")
        else:
            return f"Sample data"
    
    async def fill_form(self, page, fields: List[Dict]) -> bool:
        """Fill form with generated data"""
        try:
            for field in fields:
                field_name = field['name']
                field_type = field['type']
                
                logger.info(f"Filling field: {field_name}")
                
                try:
                    selector = f"[name='{field_name}']"
                    element = await page.query_selector(selector)
                    
                    if not element:
                        logger.warning(f"Could not find element for {field_name}")
                        continue
                    
                    value = self.generate_field_value(field_name, field_type)
                    
                    if field_type == 'checkbox':
                        await element.check()
                    elif field_type == 'radio':
                        await element.check()
                    elif field_type == 'select':
                        options = await page.query_selector_all(f"{selector} option")
                        if options:
                            first_option = options[0]
                            option_value = await first_option.get_attribute('value')
                            await page.select_option(selector, option_value)
                    else:
                        await element.fill(value)
                    
                    await page.wait_for_timeout(200)
                    
                except Exception as e:
                    logger.error(f"Error filling field {field_name}: {str(e)}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"Error in fill_form: {str(e)}")
            return False
    
    async def submit_form(self, page) -> Tuple[bool, str]:
        """Submit the form by clicking submit button"""
        try:
            submit_button = await page.query_selector(
                'button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Send")'
            )
            
            if not submit_button:
                logger.warning("Could not find submit button")
                return False, "Submit button not found"
            
            logger.info("Clicking submit button")
            await submit_button.click()
            
            try:
                await page.wait_for_load_state('networkidle', timeout=5000)
            except:
                logger.info("Network idle timeout")
            
            await page.wait_for_timeout(1000)
            
            # Check for success indicators
            content = await page.content()
            success_indicators = [
                'success', 'thank you', 'submitted successfully',
                'message sent', 'received', 'confirmed',
            ]
            
            content_lower = content.lower()
            for indicator in success_indicators:
                if indicator in content_lower:
                    logger.info(f"Found success indicator: {indicator}")
                    return True, f"Form submitted - detected: {indicator}"
            
            return True, "Form submitted successfully"
            
        except Exception as e:
            logger.error(f"Error submitting form: {str(e)}")
            return False, str(e)
    
    async def process_website(self, base_url: str) -> Dict:
        """Complete process for a single website"""
        result = {
            'url': base_url,
            'status': 'error',
            'contact_page': None,
            'fields_detected': [],
            'captcha_detected': False,
            'submission_result': None,
            'message': '',
            'timestamp': datetime.now().isoformat(),
        }
        
        page = None
        try:
            logger.info(f"=== Processing {base_url} ===")
            
            # Step 1: Find contact page
            contact_url, form_html = await self.find_contact_page(base_url)
            
            if not contact_url:
                result['message'] = "Could not find contact page"
                result['status'] = 'no_contact_page'
                return result
            
            result['contact_page'] = contact_url
            logger.info(f"Found contact page: {contact_url}")
            
            # Step 2: Open contact page
            page = await self.browser.new_page()
            await page.goto(contact_url, wait_until='networkidle')
            
            # Step 3: Check for CAPTCHA
            if await self.detect_captcha(page):
                result['captcha_detected'] = True
                result['status'] = 'captcha_detected'
                result['message'] = "CAPTCHA present - skipping"
                logger.warning("CAPTCHA detected, skipping this website")
                return result
            
            # Step 4: Extract form fields
            fields = await self.extract_form_fields(page)
            
            if not fields:
                result['message'] = "No form fields found"
                result['status'] = 'no_form_fields'
                return result
            
            result['fields_detected'] = [f['name'] for f in fields]
            logger.info(f"Found {len(fields)} fields")
            
            # Step 5: Fill form
            fill_success = await self.fill_form(page, fields)
            
            if not fill_success:
                result['message'] = "Failed to fill form fields"
                result['status'] = 'fill_failed'
                return result
            
            # Step 6: Submit form
            submit_success, submit_message = await self.submit_form(page)
            
            result['submission_result'] = submit_message
            if submit_success:
                result['status'] = 'success'
                logger.info("Form submission successful")
            else:
                result['status'] = 'submission_failed'
                logger.error(f"Form submission failed: {submit_message}")
            
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            result['message'] = str(e)
            result['status'] = 'error'
            return result
        
        finally:
            if page:
                await page.close()
    
    async def process_batch(self, urls: List[str]) -> List[Dict]:
        """Process multiple websites"""
        results = []
        for url in urls:
            result = await self.process_website(url)
            results.append(result)
        return results


# ============= USAGE EXAMPLE =============

async def main():
    filler = PlaywrightFormFiller(headless=True)
    
    try:
        await filler.initialize()
        
        urls = [
            "https://example.com",
        ]
        
        results = await filler.process_batch(urls)
        
        for result in results:
            print(json.dumps(result, indent=2))
    
    finally:
        await filler.close()


if __name__ == "__main__":
    asyncio.run(main())
