from difflib import SequenceMatcher
from selenium import webdriver
from selenium.webdriver.common.by import By
import logging

logger = logging.getLogger(__name__)

def fuzzy_match(text1, text2, threshold=0.6):
    """Check if two strings are similar enough"""
    if not text1 or not text2:
        return False
    ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    return ratio >= threshold

def extract_form_fields(driver):
    """Scrape all input fields from the page with their labels and attributes"""
    fields = []
    try:
        inputs = driver.find_elements(By.TAG_NAME, "input")
        textareas = driver.find_elements(By.TAG_NAME, "textarea")
        selects = driver.find_elements(By.TAG_NAME, "select")
        
        all_elements = inputs + textareas + selects
        
        for elem in all_elements:
            field_info = {
                "name": elem.get_attribute("name") or "",
                "id": elem.get_attribute("id") or "",
                "placeholder": elem.get_attribute("placeholder") or "",
                "type": elem.get_attribute("type") or "text",
                "label": "",
            }
            
            # Try to find associated label
            if field_info["id"]:
                try:
                    label = driver.find_element(By.CSS_SELECTOR, f"label[for='{field_info['id']}']")
                    field_info["label"] = label.text
                except:
                    pass
            
            fields.append(field_info)
        
        logger.info(f"Extracted {len(fields)} form fields from page")
        return fields
    except Exception as e:
        logger.error(f"Error extracting form fields: {e}")
        return []

def intelligent_map_fields(live_fields, cluster_labels):
    """
    Map cluster_labels (full_name, email, message, subject) 
    to actual form field names using fuzzy matching
    
    cluster_labels = ["full_name", "email", "message", "subject"]
    live_fields = [{"name": "your-name", "placeholder": "Enter your name", ...}, ...]
    """
    mapping = {}
    
    cluster_to_keywords = {
        "full_name": ["name", "full name", "first name", "your name", "contact name"],
        "email": ["email", "e-mail", "mail", "your email"],
        "message": ["message", "comment", "details", "description", "inquiry", "your message", "body"],
        "subject": ["subject", "title", "topic", "reason"],
        "phone": ["phone", "mobile", "contact number", "telephone"],
    }
    
    for cluster in cluster_labels:
        best_match = None
        best_score = 0
        keywords = cluster_to_keywords.get(cluster, [cluster])
        
        for field in live_fields:
            # Search in name, placeholder, label, id
            search_text = " ".join([
                field.get("name", ""),
                field.get("placeholder", ""),
                field.get("label", ""),
                field.get("id", ""),
            ]).lower()
            
            # Score based on keyword matches
            for keyword in keywords:
                if fuzzy_match(search_text, keyword, threshold=0.5):
                    score = SequenceMatcher(None, search_text, keyword).ratio()
                    if score > best_score:
                        best_score = score
                        best_match = field["name"]  # Use 'name' attribute as canonical
        
        if best_match:
            mapping[cluster] = best_match
            logger.info(f"Mapped {cluster} → {best_match} (score: {best_score:.2f})")
        else:
            logger.warning(f"Could not map {cluster} to any live field")
    
    return mapping

def get_smart_mapping(driver, website_id=None):
    """
    Main function: extract live fields and intelligently map them
    Returns: {"full_name": "your-name", "email": "your-email", ...}
    """
    live_fields = extract_form_fields(driver)
    
    if not live_fields:
        logger.warning("No form fields found on page")
        return {}
    
    cluster_labels = ["full_name", "email", "message", "subject", "phone"]
    mapping = intelligent_map_fields(live_fields, cluster_labels)
    
    logger.info(f"Smart mapping result: {mapping}")
    return mapping
