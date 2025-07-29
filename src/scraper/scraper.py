"""
Core scraper module.

This module handles the main scraping logic, including:
- Sending HTTP requests to target URLs.
- Handling pagination and dynamic content.
- Extracting raw data for further processing.
"""

import requests
from src.parser import parse_data
from src.storage import save_data
from src.utils import log_message

def scrape(url, output_path):
    """
    Scrape data from the given URL and save it to the specified output path.

    Args:
        url (str): The target URL to scrape.
        output_path (str): The file path to save the scraped data.

    Returns:
        None
    """
    try:
        log_message(f"Starting scrape for URL: {url}")
        response = requests.get(url)
        response.raise_for_status()
        raw_data = response.text
        parsed_data = parse_data(raw_data)
        save_data(parsed_data, output_path)
        log_message(f"Scraping completed successfully for URL: {url}")
    except requests.exceptions.RequestException as e:
        log_message(f"Error during scraping: {e}")
        raise
