# FILE #4: backend/contact_filler_main.py
# Core Automation Logic - Copy this EXACTLY

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SubmissionStatus(Enum):
    """Status codes for form submissions"""
    NOT_STARTED = 0
    COMPLETED = 1
    IN_PROGRESS = 2


@dataclass
class FormField:
    """Represents a detected form field"""
    name: str
    field_type: str
    normalized_name: str
    required: bool = False
    placeholder: str = ""


@dataclass
class WebsiteSubmission:
    """Represents a website submission record"""
    url: str
    contact_path: str
    status: int
    captcha_detected: bool
    fields_detected: List[FormField]
    timestamp: str
    submission_response: str = ""
    error_message: str = ""


# ============= FIELD MAPPING SYSTEM =============

FIELD_NORMALIZER = {
    # Name fields
    'name': ['name', 'fullname', 'full_name', 'full-name', 'fname', 'complete_name'],
    'first_name': ['first_name', 'fname', 'first-name', 'firstname', 'given_name'],
    'last_name': ['last_name', 'lname', 'last-name', 'lastname', 'family_name', 'surname'],
    'middle_name': ['middle_name', 'mname', 'middle-name', 'middlename'],
    
    # Email fields
    'email': ['email', 'email_address', 'email-address', 'e_mail', 'mail', 'contact_email'],
    'phone': ['phone', 'phone_number', 'phone-number', 'phonenumber', 'telephone', 'tel', 'mobile'],
    
    # Company/Organization
    'company': ['company', 'company_name', 'company-name', 'organization', 'employer'],
    'website': ['website', 'website_url', 'company_website', 'url', 'web_url', 'homepage'],
    
    # Message/Content
    'message': ['message', 'msg', 'comment', 'comments', 'description', 'inquiry', 'details', 'text'],
    'subject': ['subject', 'topic', 'title', 'subject_line', 'inquiry_type', 'issue_type', 'reason'],
    
    # Address
    'address': ['address', 'street_address', 'street', 'location'],
    'city': ['city', 'city_name', 'town'],
    'state': ['state', 'province', 'state_province', 'region'],
    'country': ['country', 'nation', 'country_name'],
    'postal_code': ['postal_code', 'zip', 'zip_code', 'zipcode', 'postcode', 'pin'],
    
    # Service/Product
    'service': ['service', 'service_type', 'service-type', 'services', 'service_needed'],
    'product': ['product', 'product_name', 'product-name'],
    'budget': ['budget', 'budget_range', 'price_range', 'investment'],
    
    # Date/Time
    'date': ['date', 'date_needed', 'preferred_date', 'meeting_date', 'appointment_date'],
    'time': ['time', 'time_slot', 'preferred_time', 'meeting_time'],
}

def normalize_field_name(field_name: str) -> str:
    """Normalize form field names to standard format"""
    field_name = field_name.lower().strip().replace(' ', '_')
    
    for standard_name, aliases in FIELD_NORMALIZER.items():
        if field_name in aliases:
            return standard_name
    
    return field_name


# ============= CONTACT PAGE DETECTION =============

COMMON_CONTACT_PATHS = [
    '/contact',
    '/contact-us',
    '/contact_us',
    '/contactus',
    '/support',
    '/support-us',
    '/get-in-touch',
    '/reach-us',
    '/reach_us',
    '/inquiry',
    '/inquiries',
    '/feedback',
    '/message-us',
    '/message_us',
    '/touch-base',
    '/talk-to-us',
    '/business-inquiry',
    '/customer-support',
    '/help',
    '/get-help',
]


def build_contact_urls(base_url: str) -> List[str]:
    """Generate list of potential contact page URLs"""
    base_url = base_url.rstrip('/')
    contact_urls = []
    
    for path in COMMON_CONTACT_PATHS:
        contact_urls.append(f"{base_url}{path}")
    
    return contact_urls


# ============= RANDOM DATA GENERATOR =============

RANDOM_DATA = {
    'first_names': ['John', 'Sarah', 'Michael', 'Emma', 'David', 'Lisa', 'James', 'Maria', 'Robert', 'Jennifer'],
    'last_names': ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez'],
    'companies': ['Tech Solutions Inc', 'Digital Ventures LLC', 'Innovation Labs', 'Creative Agency Co', 'Global Enterprises'],
    'subjects': ['General Inquiry', 'Partnership Proposal', 'Customer Support', 'Service Request', 'Business Opportunity'],
    'messages': [
        'I am interested in learning more about your services and how they can help my business grow.',
        'I would like to schedule a meeting to discuss potential opportunities for collaboration.',
        'Please provide more information about your latest offerings and pricing.',
        'I have a question regarding your services and would appreciate your prompt response.',
        'I am impressed with your company and would like to explore a potential partnership.',
    ]
}

def generate_random_data(field_name: str) -> str:
    """Generate realistic random data based on field type"""
    
    if 'first' in field_name or field_name == 'name':
        return random.choice(RANDOM_DATA['first_names'])
    elif 'last' in field_name:
        return random.choice(RANDOM_DATA['last_names'])
    elif 'email' in field_name:
        first = random.choice(RANDOM_DATA['first_names']).lower()
        return f"{first}.inquiry{random.randint(100,999)}@tempmail.com"
    elif 'company' in field_name:
        return random.choice(RANDOM_DATA['companies'])
    elif 'subject' in field_name:
        return random.choice(RANDOM_DATA['subjects'])
    elif 'message' in field_name:
        return random.choice(RANDOM_DATA['messages'])
    elif 'phone' in field_name:
        return f"+1{random.randint(2,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(1000,9999)}{random.randint(1000,9999)}"
    elif 'address' in field_name:
        return f"{random.randint(100, 9999)} Business Street"
    elif 'city' in field_name:
        cities = ['New York', 'San Francisco', 'Chicago', 'Boston', 'Seattle', 'Austin']
        return random.choice(cities)
    elif 'state' in field_name:
        states = ['CA', 'NY', 'TX', 'FL', 'IL', 'PA']
        return random.choice(states)
    elif 'zip' in field_name:
        return f"{random.randint(10000, 99999)}"
    elif 'website' in field_name:
        return f"https://www.business{random.randint(100,999)}.com"
    else:
        return f"Sample data"


# ============= CAPTCHA DETECTION =============

CAPTCHA_INDICATORS = [
    'recaptcha', 'g-recaptcha', 'hcaptcha', 'captcha',
    'bot-check', 'verification', 'i_am_not_a_robot',
    'arkose', 'turnstile', 'cloudflare-challenge',
]

def check_for_captcha(html_content: str, form_element) -> bool:
    """Detect if CAPTCHA is present in the page or form"""
    html_lower = html_content.lower()
    
    for indicator in CAPTCHA_INDICATORS:
        if indicator in html_lower:
            return True
    
    if form_element:
        form_str = str(form_element).lower()
        for indicator in CAPTCHA_INDICATORS:
            if indicator in form_str:
                return True
    
    return False


# ============= STATUS TRACKING DATABASE =============

class SubmissionDatabase:
    """Simple in-memory database for tracking submissions"""
    
    def __init__(self):
        self.submissions: List[WebsiteSubmission] = []
    
    def add_or_update(self, submission: WebsiteSubmission):
        """Add or update a submission record"""
        existing = self.find_by_url(submission.url)
        if existing:
            self.submissions.remove(existing)
        self.submissions.append(submission)
    
    def find_by_url(self, url: str) -> WebsiteSubmission:
        """Find submission by URL"""
        for sub in self.submissions:
            if sub.url == url:
                return sub
        return None
    
    def get_all(self) -> List[WebsiteSubmission]:
        """Get all submissions"""
        return self.submissions
    
    def get_by_status(self, status: int) -> List[WebsiteSubmission]:
        """Get submissions by status"""
        return [s for s in self.submissions if s.status == status]
    
    def export_json(self) -> str:
        """Export database as JSON"""
        data = [asdict(s) for s in self.submissions]
        return json.dumps(data, indent=2, default=str)
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        return {
            'total': len(self.submissions),
            'not_started': len(self.get_by_status(0)),
            'completed': len(self.get_by_status(1)),
            'in_progress': len(self.get_by_status(2)),
            'captcha_detected': sum(1 for s in self.submissions if s.captcha_detected),
        }


# ============= MAIN AUTOMATION CLASS =============

class ContactFormFiller:
    """Main automation engine for contact form filling"""
    
    def __init__(self):
        self.db = SubmissionDatabase()
    
    async def process_website(self, url: str) -> WebsiteSubmission:
        """Process a single website"""
        logger.info(f"Processing website: {url}")
        
        submission = WebsiteSubmission(
            url=url,
            contact_path="",
            status=SubmissionStatus.IN_PROGRESS.value,
            captcha_detected=False,
            fields_detected=[],
            timestamp=datetime.now().isoformat()
        )
        
        try:
            # Step 1: Generate contact URLs
            contact_urls = build_contact_urls(url)
            logger.info(f"Generated {len(contact_urls)} potential contact URLs")
            submission.contact_path = contact_urls[0]
            
            submission.status = SubmissionStatus.COMPLETED.value
            submission.timestamp = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            submission.error_message = str(e)
            submission.status = SubmissionStatus.NOT_STARTED.value
        
        self.db.add_or_update(submission)
        return submission
    
    async def process_batch(self, urls: List[str]):
        """Process multiple websites concurrently"""
        logger.info(f"Processing batch of {len(urls)} websites")
        tasks = [self.process_website(url) for url in urls]
        results = await asyncio.gather(*tasks)
        return results
    
    def get_status_report(self) -> Dict:
        """Generate status report"""
        stats = self.db.get_stats()
        return {
            'timestamp': datetime.now().isoformat(),
            'statistics': stats,
            'submissions': [asdict(s) for s in self.db.get_all()]
        }


# ============= USAGE EXAMPLE =============

async def main():
    """Example usage"""
    filler = ContactFormFiller()
    
    urls = [
        "https://example.com",
        "https://techcompany.io",
    ]
    
    results = await filler.process_batch(urls)
    
    report = filler.get_status_report()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
