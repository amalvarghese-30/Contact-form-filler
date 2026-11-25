# FILE #8: backend/database.py
# Database Setup & URL Management - Copy this EXACTLY

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os

logger = logging.getLogger(__name__)

# Database file location
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'urls.db')


class URLDatabase:
    """SQLite database for storing company URLs and form data"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.ensure_db_exists()
    
    def ensure_db_exists(self):
        """Create database and tables if they don't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table 1: Company URLs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company_urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                company_name TEXT,
                industry TEXT,
                country TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed INTEGER DEFAULT 0,
                contact_page_found INTEGER DEFAULT 0,
                has_captcha INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                fields_found TEXT,
                notes TEXT
            )
        ''')
        
        # Table 2: Form Field Analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_id INTEGER NOT NULL,
                field_name TEXT,
                field_type TEXT,
                normalized_name TEXT,
                placeholder TEXT,
                required INTEGER,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(url_id) REFERENCES company_urls(id)
            )
        ''')
        
        # Table 3: Field Mapping Analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS field_mapping_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                normalized_name TEXT UNIQUE,
                field_variations TEXT,
                common_placeholders TEXT,
                frequency INTEGER DEFAULT 0,
                data_type TEXT,
                examples TEXT,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table 4: Processing Queue
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processing_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                result TEXT,
                FOREIGN KEY(url_id) REFERENCES company_urls(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized")
    
    def add_url(self, url: str, company_name: str = None, industry: str = None, country: str = None) -> int:
        """Add a single URL to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO company_urls (url, company_name, industry, country)
                VALUES (?, ?, ?, ?)
            ''', (url, company_name, industry, country))
            
            conn.commit()
            url_id = cursor.lastrowid
            conn.close()
            
            logger.info(f"Added URL: {url} (ID: {url_id})")
            return url_id
        
        except sqlite3.IntegrityError:
            logger.warning(f"URL already exists: {url}")
            return None
        except Exception as e:
            logger.error(f"Error adding URL: {e}")
            return None
    
    def add_urls_batch(self, urls: List[Dict]) -> int:
        """Add multiple URLs at once"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            added = 0
            for item in urls:
                try:
                    cursor.execute('''
                        INSERT INTO company_urls (url, company_name, industry, country)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        item.get('url'),
                        item.get('company_name'),
                        item.get('industry'),
                        item.get('country')
                    ))
                    added += 1
                except sqlite3.IntegrityError:
                    pass
            
            conn.commit()
            conn.close()
            
            logger.info(f"Added {added} URLs to database")
            return added
        
        except Exception as e:
            logger.error(f"Error adding batch URLs: {e}")
            return 0
    
    def get_pending_urls(self, limit: int = 50) -> List[Dict]:
        """Get unprocessed URLs from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, url, company_name, industry, country
                FROM company_urls
                WHERE processed = 0 AND status = 'pending'
                ORDER BY added_at ASC
                LIMIT ?
            ''', (limit,))
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            logger.info(f"Retrieved {len(results)} pending URLs")
            return results
        
        except Exception as e:
            logger.error(f"Error getting pending URLs: {e}")
            return []
    
    def get_all_urls(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get all URLs from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if limit:
                cursor.execute('''
                    SELECT id, url, company_name, industry, country, processed, status
                    FROM company_urls
                    ORDER BY added_at DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))
            else:
                cursor.execute('''
                    SELECT id, url, company_name, industry, country, processed, status
                    FROM company_urls
                    ORDER BY added_at DESC
                ''')
            
            results = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            return results
        
        except Exception as e:
            logger.error(f"Error getting all URLs: {e}")
            return []
    
    def update_url_status(self, url_id: int, status: str, processed: int = 1):
        """Update URL processing status"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE company_urls
                SET status = ?, processed = ?, contact_page_found = ?
                WHERE id = ?
            ''', (status, processed, 1 if status == 'success' else 0, url_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated URL {url_id} status to {status}")
        
        except Exception as e:
            logger.error(f"Error updating URL status: {e}")
    
    def add_form_field(self, url_id: int, field_name: str, field_type: str, 
                       normalized_name: str, placeholder: str = None, required: bool = False):
        """Add discovered form field to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO form_fields 
                (url_id, field_name, field_type, normalized_name, placeholder, required)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (url_id, field_name, field_type, normalized_name, placeholder, int(required)))
            
            conn.commit()
            conn.close()
        
        except Exception as e:
            logger.error(f"Error adding form field: {e}")
    
    def get_database_stats(self) -> Dict:
        """Get overall database statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Total URLs
            cursor.execute('SELECT COUNT(*) as count FROM company_urls')
            total_urls = cursor.fetchone()['count']
            
            # Processed URLs
            cursor.execute('SELECT COUNT(*) as count FROM company_urls WHERE processed = 1')
            processed_urls = cursor.fetchone()['count']
            
            # With contact pages
            cursor.execute('SELECT COUNT(*) as count FROM company_urls WHERE contact_page_found = 1')
            with_contact = cursor.fetchone()['count']
            
            # With CAPTCHA
            cursor.execute('SELECT COUNT(*) as count FROM company_urls WHERE has_captcha = 1')
            with_captcha = cursor.fetchone()['count']
            
            # Total fields discovered
            cursor.execute('SELECT COUNT(*) as count FROM form_fields')
            total_fields = cursor.fetchone()['count']
            
            # By status
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM company_urls 
                GROUP BY status
            ''')
            status_breakdown = {row['status']: row['count'] for row in cursor.fetchall()}
            
            conn.close()
            
            return {
                'total_urls': total_urls,
                'processed_urls': processed_urls,
                'pending_urls': total_urls - processed_urls,
                'with_contact_pages': with_contact,
                'with_captcha': with_captcha,
                'total_form_fields_discovered': total_fields,
                'status_breakdown': status_breakdown,
                'percentage_complete': round((processed_urls / total_urls * 100) if total_urls > 0 else 0, 2)
            }
        
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}
    
    def get_field_mapping_summary(self) -> Dict:
        """Analyze and return field mapping summary"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all normalized fields with their variations
            cursor.execute('''
                SELECT normalized_name, GROUP_CONCAT(DISTINCT field_name, ', ') as variations, 
                       COUNT(*) as frequency, field_type
                FROM form_fields
                GROUP BY normalized_name
                ORDER BY frequency DESC
            ''')
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'normalized_name': row['normalized_name'],
                    'field_name_variations': row['variations'].split(', ') if row['variations'] else [],
                    'frequency': row['frequency'],
                    'common_type': row['field_type']
                })
            
            conn.close()
            return results
        
        except Exception as e:
            logger.error(f"Error getting field mapping summary: {e}")
            return []


class FieldAnalyzer:
    """Analyze form fields and group similar ones"""
    
    # Predefined field groups with all their variations
    FIELD_GROUPS = {
        'first_name': {
            'variations': ['fname', 'first_name', 'firstname', 'first-name', 'given_name', 'given-name', 'firstname_name'],
            'description': 'Person\'s first/given name',
            'data_type': 'text',
            'example': 'John'
        },
        'last_name': {
            'variations': ['lname', 'last_name', 'lastname', 'last-name', 'family_name', 'family-name', 'surname', 'sur_name'],
            'description': 'Person\'s last/family name',
            'data_type': 'text',
            'example': 'Smith'
        },
        'full_name': {
            'variations': ['name', 'fullname', 'full_name', 'full-name', 'complete_name', 'your_name', 'contact_name'],
            'description': 'Complete person name',
            'data_type': 'text',
            'example': 'John Smith'
        },
        'email': {
            'variations': ['email', 'email_address', 'email-address', 'e_mail', 'mail', 'contact_email', 'from_email', 'recipient_email'],
            'description': 'Email address',
            'data_type': 'email',
            'example': 'john@example.com'
        },
        'phone': {
            'variations': ['phone', 'phone_number', 'phone-number', 'phonenumber', 'telephone', 'tel', 'mobile', 'mobile_number', 'contact_number', 'phone_num', 'cell'],
            'description': 'Phone number',
            'data_type': 'tel',
            'example': '+1-555-123-4567'
        },
        'company': {
            'variations': ['company', 'company_name', 'company-name', 'organization', 'org', 'org_name', 'business', 'business_name', 'employer', 'employer_name', 'firm'],
            'description': 'Company/organization name',
            'data_type': 'text',
            'example': 'Acme Corp'
        },
        'job_title': {
            'variations': ['job_title', 'jobtitle', 'title', 'position', 'designation', 'role', 'job_role', 'occupation'],
            'description': 'Job title/position',
            'data_type': 'text',
            'example': 'Manager'
        },
        'website': {
            'variations': ['website', 'website_url', 'company_website', 'url', 'web_url', 'homepage', 'web_address', 'company_url'],
            'description': 'Website URL',
            'data_type': 'url',
            'example': 'https://example.com'
        },
        'message': {
            'variations': ['message', 'msg', 'comment', 'comments', 'description', 'inquiry', 'question', 'content', 'text', 'details', 'information', 'body', 'request', 'feedback', 'notes', 'remarks', 'message_body'],
            'description': 'Message/inquiry text',
            'data_type': 'textarea',
            'example': 'I am interested in your services'
        },
        'subject': {
            'variations': ['subject', 'topic', 'title', 'subject_line', 'inquiry_type', 'issue_type', 'reason', 'category', 'type', 'reason_for_contact', 'subject_type'],
            'description': 'Message subject/topic',
            'data_type': 'text',
            'example': 'General Inquiry'
        },
        'address': {
            'variations': ['address', 'street_address', 'street-address', 'street', 'location', 'city_address', 'full_address', 'residential_address'],
            'description': 'Street address',
            'data_type': 'text',
            'example': '123 Main Street'
        },
        'city': {
            'variations': ['city', 'city_name', 'town', 'city_town', 'locality'],
            'description': 'City/town name',
            'data_type': 'text',
            'example': 'New York'
        },
        'state': {
            'variations': ['state', 'province', 'state_province', 'region', 'state_or_province', 'region_name'],
            'description': 'State/province',
            'data_type': 'text',
            'example': 'NY'
        },
        'country': {
            'variations': ['country', 'nation', 'country_name', 'nation_name'],
            'description': 'Country name',
            'data_type': 'select',
            'example': 'United States'
        },
        'postal_code': {
            'variations': ['postal_code', 'zip', 'zip_code', 'zipcode', 'postcode', 'post_code', 'pin', 'pin_code', 'postal_code_zip'],
            'description': 'Postal/ZIP code',
            'data_type': 'text',
            'example': '10001'
        },
        'service': {
            'variations': ['service', 'service_type', 'service-type', 'services', 'service_needed', 'type_of_service', 'which_service'],
            'description': 'Type of service interested in',
            'data_type': 'select',
            'example': 'Consulting'
        },
        'product': {
            'variations': ['product', 'product_name', 'product-name', 'product_type', 'which_product'],
            'description': 'Product name/type',
            'data_type': 'text',
            'example': 'Software Solution'
        },
        'budget': {
            'variations': ['budget', 'budget_range', 'price_range', 'investment', 'spending', 'budget_size', 'expected_budget'],
            'description': 'Budget range',
            'data_type': 'select',
            'example': '$10,000 - $50,000'
        },
        'date': {
            'variations': ['date', 'date_needed', 'date-needed', 'preferred_date', 'meeting_date', 'appointment_date', 'start_date', 'event_date'],
            'description': 'Date field',
            'data_type': 'date',
            'example': '2025-12-15'
        },
        'time': {
            'variations': ['time', 'time_slot', 'preferred_time', 'meeting_time', 'appointment_time', 'start_time'],
            'description': 'Time field',
            'data_type': 'time',
            'example': '14:30'
        },
        'industry': {
            'variations': ['industry', 'industry_type', 'industry_name', 'business_type', 'sector'],
            'description': 'Industry/business sector',
            'data_type': 'select',
            'example': 'Technology'
        },
        'number_of_employees': {
            'variations': ['employees', 'num_employees', 'number_of_employees', 'employee_count', 'company_size', 'staff_size'],
            'description': 'Company employee count',
            'data_type': 'select',
            'example': '50-100'
        },
        'annual_revenue': {
            'variations': ['revenue', 'annual_revenue', 'yearly_revenue', 'revenue_range', 'annual_turnover'],
            'description': 'Annual revenue',
            'data_type': 'text',
            'example': '$1M - $5M'
        }
    }
    
    @staticmethod
    def normalize_field_name(field_name: str) -> str:
        """Normalize a field name to standard format"""
        field_name = field_name.lower().strip().replace(' ', '_').replace('-', '_')
        
        for standard_name, config in FieldAnalyzer.FIELD_GROUPS.items():
            if field_name in config['variations']:
                return standard_name
        
        return field_name
    
    @staticmethod
    def get_all_field_groups() -> Dict:
        """Get all field groups with descriptions"""
        return FieldAnalyzer.FIELD_GROUPS
    
    @staticmethod
    def generate_field_statistics(db_results: List[Dict]) -> Dict:
        """Generate statistics from database results"""
        stats = {
            'total_unique_fields': 0,
            'total_field_instances': len(db_results),
            'field_groups': {},
            'most_common_fields': [],
            'unused_groups': []
        }
        
        # Count field instances
        field_counts = {}
        for result in db_results:
            normalized = result['normalized_name']
            field_counts[normalized] = field_counts.get(normalized, 0) + 1
        
        # Organize by groups
        for standard_name, config in FieldAnalyzer.FIELD_GROUPS.items():
            count = field_counts.get(standard_name, 0)
            
            stats['field_groups'][standard_name] = {
                'count': count,
                'description': config['description'],
                'data_type': config['data_type'],
                'example': config['example'],
                'variations_found': [v for v in config['variations'] if v in [r['field_name_variations'][0] if r['field_name_variations'] else '' for r in db_results]]
            }
            
            if count == 0:
                stats['unused_groups'].append(standard_name)
        
        # Top 10 most common fields
        stats['most_common_fields'] = sorted(
            field_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        stats['total_unique_fields'] = len(field_counts)
        
        return stats
