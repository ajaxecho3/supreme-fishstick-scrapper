# Usage Guide

## Running the Scraper

1. Activate the virtual environment:

    ```bash
    source .venv/bin/activate
    ```

2. Run the scraper:

    ```bash
    python src/scraper.py
    ```

## Configuration

Edit the `config/config.json` file to customize settings like timeout, output directory, and proxy/user-agent files.

## Output

Scraped data will be saved in the `data/output` directory.

## Logs

Check `logs/scraper.log` for detailed logs and error tracking.
