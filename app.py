from flask import Flask, jsonify, request, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import random
import os
from urllib.parse import quote_plus 
from PIL import Image, ImageDraw, ImageFont

# Initialize Flask app
app = Flask(__name__)

# ---- Build DB URL from Railway envs (preferred), or DATABASE_URL, else SQLite fallback ----
MYSQL_HOST = os.getenv('MYSQLHOST')
MYSQL_PORT = os.getenv('MYSQLPORT', '3306')
MYSQL_USER = os.getenv('MYSQLUSER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQLPASSWORD')
MYSQL_DATABASE = os.getenv('MYSQLDATABASE', 'railway')


def _clean(v):
    return v.strip().strip('"').strip("'") if v else v

def _looks_like_sqlalchemy_url(url: str) -> bool:
    if not url:
        return False
    u = url.lower().strip()
    return u.startswith("mysql://") or u.startswith("mysql+pymysql://") or u.startswith("mysql+mysqlconnector://") or u.startswith("sqlite:///")


DATABASE_URL = None

if MYSQL_HOST and MYSQL_PASSWORD and MYSQL_DATABASE:
    encoded_password = quote_plus(MYSQL_PASSWORD)
    DATABASE_URL = f"mysql+pymysql://{_clean(MYSQL_USER)}:{encoded_password}@{_clean(MYSQL_HOST)}:{_clean(MYSQL_PORT)}/{_clean(MYSQL_DATABASE)}"
    print("✅ Using deployment database (Railway parts)")
else:
    raw = _clean(os.getenv('DATABASE_URL') or os.getenv('DB_URL') or os.getenv('MYSQL_URL') or os.getenv('MYSQLURL'))
    if raw and _looks_like_sqlalchemy_url(raw):
        # Normalize to PyMySQL if it's a MySQL URL
        if raw.startswith('mysql://'):
            raw = raw.replace('mysql://', 'mysql+pymysql://', 1)
        if raw.startswith('mysql+mysqlconnector://'):
            raw = raw.replace('mysql+mysqlconnector://', 'mysql+pymysql://', 1)
        DATABASE_URL = raw
        print("✅ Using deployment database (full URL)")
    else:
        # Local dev fallback (no MySQL required)
        DATABASE_URL = "sqlite:///country_api.db"
        print("⚠️ Using local SQLite database (no Railway DB vars found)")

print("DB URI (sanitized):", (DATABASE_URL.split('@')[0] + "@***") if "@" in DATABASE_URL else DATABASE_URL)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Keep connections healthy on Railway
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {"pool_pre_ping": True, "pool_recycle": 280}

# External APIs
COUNTRIES_API = "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
EXCHANGE_RATE_API = "https://open.er-api.com/v6/latest/USD"

# Cache directory for images
CACHE_DIR = "cache"

# API timeout in seconds
API_TIMEOUT = 10

# Flask secret key (for sessions)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Initialize database
db = SQLAlchemy(app)  # <-- fixed )

# ==================== DATABASE MODELS ====================

class Country(db.Model):
    """Country model representing cached country data"""
    __tablename__ = 'countries'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    capital = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(50), nullable=True)
    population = db.Column(db.BigInteger, nullable=False, default=0)
    currency_code = db.Column(db.String(10), nullable=True)
    exchange_rate = db.Column(db.Float, nullable=True)
    estimated_gdp = db.Column(db.Float, nullable=True)
    flag_url = db.Column(db.String(255), nullable=True)
    last_refreshed_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert model to dictionary for JSON responses"""
        return {
            'id': self.id,
            'name': self.name,
            'capital': self.capital,
            'region': self.region,
            'population': self.population,
            'currency_code': self.currency_code,
            'exchange_rate': self.exchange_rate,
            'estimated_gdp': self.estimated_gdp,
            'flag_url': self.flag_url,
            'last_refreshed_at': self.last_refreshed_at.isoformat() + 'Z' if self.last_refreshed_at else None
        }
    
    def __repr__(self):
        return f'<Country {self.name}>'


class RefreshMetadata(db.Model):
    """Track global refresh timestamp"""
    __tablename__ = 'refresh_metadata'
    
    id = db.Column(db.Integer, primary_key=True)
    last_refreshed_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_countries = db.Column(db.Integer, default=0)
    
    def to_dict(self):
        return {
            'total_countries': self.total_countries,
            'last_refreshed_at': self.last_refreshed_at.isoformat() + 'Z' if self.last_refreshed_at else None
        }

# Create tables and cache directory
with app.app_context():
    os.makedirs(CACHE_DIR, exist_ok=True)
    try:
        db.create_all()
    except Exception as e:
        app.logger.error(f"DB init failed: {e}")

# ==================== HELPER FUNCTIONS ====================

def calculate_gdp(population, exchange_rate):
    """Calculate estimated GDP using the formula from requirements"""
    if not population or not exchange_rate:
        return None
    multiplier = random.uniform(1000, 2000)
    return (population * multiplier) / exchange_rate

def generate_summary_image(countries_data):
    """Generate a summary image with country statistics"""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a nice font, fall back to default if not available
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except Exception:
        try:
            # Windows font path
            title_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 32)
            text_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 20)
        except Exception:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
    
    # Title
    draw.text((50, 30), "Country Data Summary", fill='black', font=title_font)
    
    # Total countries
    total = len(countries_data)
    draw.text((50, 100), f"Total Countries: {total}", fill='black', font=text_font)
    
    # Sort by GDP descending and take top 5
    top_countries = sorted(
        [c for c in countries_data if c.estimated_gdp],
        key=lambda x: x.estimated_gdp,
        reverse=True
    )[:5]
    
    # Draw top 5 countries
    draw.text((50, 150), "Top 5 by Estimated GDP:", fill='black', font=text_font)
    y_pos = 190
    for i, country in enumerate(top_countries, 1):
        gdp_formatted = f"{country.estimated_gdp:,.2f}"
        text = f"{i}. {country.name}: ${gdp_formatted}"
        draw.text((70, y_pos), text, fill='darkblue', font=text_font)
        y_pos += 40
    
    # Timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    draw.text((50, 500), f"Last Updated: {timestamp}", fill='gray', font=text_font)
    
    # Save image
    image_path = os.path.join(CACHE_DIR, 'summary.png')
    img.save(image_path)
    return image_path

# ==================== API ENDPOINTS ====================

@app.route('/')
def home():
    return "Welcome to my Country currency API"

@app.route('/countries/refresh', methods=['POST'])
def refresh_countries():
    """Fetch data from external APIs and update database"""
    try:
        countries_response = requests.get(COUNTRIES_API, timeout=API_TIMEOUT)
        countries_response.raise_for_status()
        countries_data = countries_response.json()
    except requests.RequestException as e:
        return jsonify({"error": "External data source unavailable",
                        "details": f"Could not fetch data from countries API: {str(e)}"}), 503
    
    try:
        exchange_response = requests.get(EXCHANGE_RATE_API, timeout=API_TIMEOUT)
        exchange_response.raise_for_status()
        exchange_data = exchange_response.json()
        exchange_rates = exchange_data.get('rates', {})
    except requests.RequestException as e:
        return jsonify({"error": "External data source unavailable",
                        "details": f"Could not fetch data from exchange rate API: {str(e)}"}), 503
    
    # Process each country
    for country_data in countries_data:
        name = country_data.get('name')
        if not name:
            continue
        
        # Extract currency code (first one if multiple exist)
        currencies = country_data.get('currencies') or []
        currency_code = None
        if currencies:
            currency_code = (currencies[0] or {}).get('code')
        
        # Get exchange rate only if currency exists
        exchange_rate = None
        estimated_gdp = None
        
        if currency_code:
            exchange_rate = exchange_rates.get(currency_code)
            population = country_data.get('population')
            if population and exchange_rate:
                estimated_gdp = calculate_gdp(population, exchange_rate)
        
        # Check if country exists (case-insensitive search)
        existing_country = Country.query.filter(
            db.func.lower(Country.name) == name.lower()
        ).first()
        
        if existing_country:
            # Update existing record
            existing_country.capital = country_data.get('capital')
            existing_country.region = country_data.get('region')
            existing_country.population = country_data.get('population') or 0
            existing_country.currency_code = currency_code
            existing_country.exchange_rate = exchange_rate
            existing_country.estimated_gdp = estimated_gdp
            existing_country.flag_url = country_data.get('flag')
            existing_country.last_refreshed_at = datetime.utcnow()
        else:
            # Create new country record
            new_country = Country(
                name=name,
                capital=country_data.get('capital'),
                region=country_data.get('region'),
                population=country_data.get('population') or 0,
                currency_code=currency_code,
                exchange_rate=exchange_rate,
                estimated_gdp=estimated_gdp,
                flag_url=country_data.get('flag'),
                last_refreshed_at=datetime.utcnow()
            )
            db.session.add(new_country)
    
    # Commit all changes to database
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500
    
    # Update global refresh metadata
    total_countries = Country.query.count()
    metadata = RefreshMetadata.query.first()
    if metadata:
        metadata.last_refreshed_at = datetime.utcnow()
        metadata.total_countries = total_countries
    else:
        metadata = RefreshMetadata(
            last_refreshed_at=datetime.utcnow(),
            total_countries=total_countries
        )
        db.session.add(metadata)
        db.session.commit()
    
    # Generate summary image
    try:
        all_countries = Country.query.all()
        generate_summary_image(all_countries)
    except Exception as e:
        app.logger.warning(f"Warning: Could not generate summary image: {e}")
    
    return jsonify({
        "message": "Countries refreshed successfully",
        "total_countries": total_countries
    }), 200

@app.route('/countries', methods=['GET'])
def get_countries():
    """Get all countries with optional filtering and sorting"""
    query = Country.query
    
    # Apply filters
    region = request.args.get('region')
    if region:
        query = query.filter(db.func.lower(Country.region) == region.lower())
    
    currency = request.args.get('currency')
    if currency:
        query = query.filter(db.func.lower(Country.currency_code) == currency.lower())
    
    # Apply sorting (MySQL-safe)
    sort = request.args.get('sort')
    if sort == 'gdp_desc':
        query = query.order_by(db.desc(Country.estimated_gdp))
    elif sort == 'gdp_asc':
        query = query.order_by(db.asc(Country.estimated_gdp))
    elif sort == 'name':
        query = query.order_by(Country.name.asc())
    
    countries = query.all()
    return jsonify([country.to_dict() for country in countries]), 200

@app.route('/countries/<string:name>', methods=['GET'])
def get_country(name):
    """Get a single country by name"""
    country = Country.query.filter(
        db.func.lower(Country.name) == name.lower()
    ).first()
    if not country:
        return jsonify({"error": "Country not found"}), 404
    return jsonify(country.to_dict()), 200

@app.route('/countries/<string:name>', methods=['DELETE'])
def delete_country(name):
    """Delete a country by name"""
    country = Country.query.filter(
        db.func.lower(Country.name) == name.lower()
    ).first()
    if not country:
        return jsonify({"error": "Country not found"}), 404
    try:
        db.session.delete(country)
        db.session.commit()
        metadata = RefreshMetadata.query.first()
        if metadata:
            metadata.total_countries = Country.query.count()
            db.session.commit()
        return jsonify({"message": f"Country '{name}' deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error", "details": str(e)}), 500

@app.route('/status', methods=['GET'])
def get_status():
    """Get total countries and last refresh timestamp"""
    metadata = RefreshMetadata.query.first()
    if not metadata:
        return jsonify({"total_countries": 0, "last_refreshed_at": None}), 200
    return jsonify(metadata.to_dict()), 200

@app.route('/countries/image', methods=['GET'])
def get_summary_image():
    """Serve the generated summary image"""
    image_path = os.path.join(CACHE_DIR, 'summary.png')
    if not os.path.exists(image_path):
        return jsonify({"error": "Summary image not found"}), 404
    return send_file(image_path, mimetype='image/png')

# ==================== ERROR HANDLERS ====================

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Validation failed"}), 400

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({"error": "Internal server error"}), 500

# ==================== RUN APPLICATION ====================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host='0.0.0.0', port=port)
