# CollectWithAkash - Diecast Store Manager

A Python and SQLite inventory management and sales analytics application for diecast collectibles, built with Streamlit.

## Features

- Inventory management and search
- Low-stock alerts
- Sales recording and overselling prevention
- Stock purchases and restocking
- Sales analytics and best-seller reports
- Financial reports and Excel exports
- PDF invoice generation
- Supplier and expense management

## Technology Stack

Python, Streamlit, SQLite, Pandas, Plotly, OpenPyXL, ReportLab, Pytest, Git, and GitHub.

## Getting Started

### Prerequisites

Python 3.11 or compatible version, and Git.

### 1. Clone the repository

    git clone https://github.com/akashkprasanth/diecast-store-manager-collectwithakash.git
    cd diecast-store-manager-collectwithakash

### 2. Create and activate a virtual environment

On Windows PowerShell:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1

### 3. Install dependencies

    python -m pip install -r requirements.txt

### 4. Start the application

    python -m streamlit run app.py

Open the local URL shown in the terminal, usually http://localhost:8501.

## Automated Tests

Eight automated tests currently pass. They cover inventory valuation, low-stock detection, stock purchases, sales, overselling prevention, and input validation.

Run the tests with:

    python -m pytest -v test_db.py

The tests use a temporary SQLite database to avoid modifying the application's existing database.

## Project Structure

- `app.py` - Streamlit application
- `db.py` - Database and inventory operations
- `inventory_management.py` - Inventory management
- `sales_analytics.py` - Sales analytics
- `best_sellers.py` - Best-seller analysis
- `business_features.py` - Supplier, expense, and financial reporting
- `invoice_generator.py` - PDF invoice generation
- `test_db.py` - Automated tests
- `requirements.txt` - Python dependencies

## Project Purpose

This is a portfolio project created to demonstrate software development skills. It is intended for demonstration and learning, not as a production-ready commercial system.

## Future Improvements

- Expand automated test coverage
- Add screenshots and demonstration data
- Deploy an online demo
- Improve error handling and documentation

## Author

CollectWithAkash

GitHub repository:
https://github.com/akashkprasanth/diecast-store-manager-collectwithakash
