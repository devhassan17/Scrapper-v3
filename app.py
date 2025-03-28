from flask import Flask, render_template, redirect, url_for, request, session, send_file
import requests
import sqlite3
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "Qwerty123!@#"

# Authentication setup (same as before)
USERNAME = "Justin"
PASSWORD = "Justin123!@#Scrapper"

def is_logged_in():
    return session.get("logged_in")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return "Invalid credentials, try again!"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def login_required(func):
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# Database setup
def setup_database():
    conn = sqlite3.connect("companies.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            scraped_at TEXT
        )
    """)
    conn.commit()
    conn.close()

# Scraping functions
def get_region_urls():
    sitemap_url = "https://www.regiogidsen.nl/category-sitemap.xml"
    response = requests.get(sitemap_url)
    if response.status_code != 200:
        return []
    
    root = ET.fromstring(response.content)
    namespaces = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    return [elem.text for elem in root.findall('.//ns:loc', namespaces)]

def scrape_company_urls(region_url):
    try:
        response = requests.get(region_url)
        if response.status_code != 200:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        company_links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('https://www.regiogidsen.nl/bedrijf/'):
                company_links.append(href)
        
        return company_links
    except Exception as e:
        print(f"Error scraping {region_url}: {e}")
        return []

def save_companies_to_db(urls):
    conn = sqlite3.connect("companies.db")
    cursor = conn.cursor()
    new_count = 0
    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for url in urls:
        try:
            cursor.execute("INSERT INTO companies (url, scraped_at) VALUES (?, ?)", (url, scraped_at))
            new_count += 1
        except sqlite3.IntegrityError:
            pass  # Skip duplicates
    
    conn.commit()
    conn.close()
    return new_count

def get_all_companies():
    conn = sqlite3.connect("companies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, url FROM companies ORDER BY id DESC")
    companies = cursor.fetchall()
    conn.close()
    return companies

def get_company_count():
    conn = sqlite3.connect("companies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM companies")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def generate_pdf():
    companies = get_all_companies()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Scraped Companies", ln=1, align='C')
    
    for company in companies:
        pdf.cell(200, 10, txt=company[1], ln=1)
    
    pdf.output("companies.pdf")
    return "companies.pdf"

# Routes
@app.route('/')
@login_required
def index():
    count = get_company_count()
    return render_template("index.html", company_count=count)

@app.route('/companies')
@login_required
def companies():
    companies = get_all_companies()
    return render_template("companies.html", companies=companies)

@app.route('/scrape', methods=['POST'])
@login_required
def scrape():
    region_urls = get_region_urls()
    all_companies = []
    
    for region_url in region_urls:
        companies = scrape_company_urls(region_url)
        all_companies.extend(companies)
    
    new_count = save_companies_to_db(all_companies)
    return redirect(url_for("index"))

@app.route('/download')
@login_required
def download():
    pdf_file = generate_pdf()
    return send_file(pdf_file, as_attachment=True)

if __name__ == "__main__":
    setup_database()
    app.run(debug=True)