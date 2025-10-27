from flask import Flask, jsonify, request, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import random
import os
from PIL import Image, ImageDraw, ImageFont

# Initialize Flask app
app = Flask(__name__)

if os.getenv('DATABASE_URL'):
    DATABASE_URL = os.getenv('DATABASE_URL')
elif os.getenv('MYSQL_URL'):
    DATABASE_URL = os.getenv('MYSQL_URL')
elif os.getenv('MYSQLURL'):
    DATABASE_URL = os.getenv('MYSQLURL')
else:
    # Local development
    DATABASE_URL = f"mysql+mysqlconnector://root:root@localhost:3306/country_api"
    print("✅ Using local database")

# Fix URL format
if DATABASE_URL and DATABASE_URL.startswith('mysql://'):
    DATABASE_URL = DATABASE_URL.replace('mysql://', 'mysql+mysqlconnector://', 1)

if 'localhost' not in DATABASE_URL:
    print("✅ Using deployment database")
else:
    print("✅ Using local database")

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# API URLs
COUNTRIES_API = "https://restcountries.com/v2/all?fields=name,capital,region,population,flag,currencies"
EXCHANGE_RATE_API = "https://open.er-api.com/v6/latest/USD"

# Cache directory for images
CACHE_DIR = "cache"

# API timeout in seconds
API_TIMEOUT = 10

# Flask secret key (for sessions)
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'

# Initialize database
db = SQLAlchemy(app)


# ==================== DATABASE MODELS ====================

class Country(db.Model):
    """Country model representing cached country data"""
    __tablename__ = 'countries'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    capital = db.Column(db.String(100), nullable=True)
    region = db.Column(db.String(50), nullable=True)
    population = db.Column(db.BigInteger, nullable=False)
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
    db.create_all()
    os.makedirs(CACHE_DIR, exist_ok=True)


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
    except:
        try:
            # Windows font path
            title_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 32)
            text_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 20)
        except:
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
    """
    Fetch data from external APIs and update database
    POST /countries/refresh
    """
    try:
        # Fetch country data
        countries_response = requests.get(COUNTRIES_API, timeout=API_TIMEOUT)
        countries_response.raise_for_status()
        countries_data = countries_response.json()
        
    except requests.RequestException as e:
        return jsonify({
            "error": "External data source unavailable",
            "details": f"Could not fetch data from countries API: {str(e)}"
        }), 503
    
    try:
        # Fetch exchange rates
        exchange_response = requests.get(EXCHANGE_RATE_API, timeout=API_TIMEOUT)
        exchange_response.raise_for_status()
        exchange_data = exchange_response.json()
        exchange_rates = exchange_data.get('rates', {})
        
    except requests.RequestException as e:
        return jsonify({
            "error": "External data source unavailable",
            "details": f"Could not fetch data from exchange rate API: {str(e)}"
        }), 503
    
    # Process each country
    for country_data in countries_data:
        name = country_data.get('name')
        if not name:
            continue
        
        # Extract currency code (first one if multiple exist)
        currencies = country_data.get('currencies', [])
        currency_code = None
        if currencies and len(currencies) > 0:
            currency_code = currencies[0].get('code')
        
        # Get exchange rate only if currency exists
        exchange_rate = None
        estimated_gdp = None
        
        if currency_code:
            exchange_rate = exchange_rates.get(currency_code)
            
            # Calculate GDP only if we have all required data
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
            existing_country.population = country_data.get('population', 0)
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
                population=country_data.get('population', 0),
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
        print(f"Warning: Could not generate summary image: {e}")
    
    return jsonify({
        "message": "Countries refreshed successfully",
        "total_countries": total_countries
    }), 200


@app.route('/countries', methods=['GET'])
def get_countries():
    """
    Get all countries with optional filtering and sorting
    GET /countries
    GET /countries?region=Africa
    GET /countries?currency=NGN
    GET /countries?sort=gdp_desc
    """
    query = Country.query
    
    # Apply filters
    region = request.args.get('region')
    if region:
        query = query.filter(db.func.lower(Country.region) == region.lower())
    
    currency = request.args.get('currency')
    if currency:
        query = query.filter(db.func.lower(Country.currency_code) == currency.lower())
    
    # Apply sorting
    sort = request.args.get('sort')
    if sort == 'gdp_desc':
        query = query.order_by(Country.estimated_gdp.desc().nullslast())
    elif sort == 'gdp_asc':
        query = query.order_by(Country.estimated_gdp.asc().nullsfirst())
    elif sort == 'name':
        query = query.order_by(Country.name)
    
    # Execute query
    countries = query.all()
    return jsonify([country.to_dict() for country in countries]), 200


@app.route('/countries/<string:name>', methods=['GET'])
def get_country(name):
    """
    Get a single country by name
    GET /countries/Nigeria
    """
    country = Country.query.filter(
        db.func.lower(Country.name) == name.lower()
    ).first()
    
    if not country:
        return jsonify({"error": "Country not found"}), 404
    
    return jsonify(country.to_dict()), 200


@app.route('/countries/<string:name>', methods=['DELETE'])
def delete_country(name):
    """
    Delete a country by name
    DELETE /countries/Nigeria
    """
    country = Country.query.filter(
        db.func.lower(Country.name) == name.lower()
    ).first()
    
    if not country:
        return jsonify({"error": "Country not found"}), 404
    
    try:
        db.session.delete(country)
        db.session.commit()
        
        # Update total count in metadata
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
    """
    Get total countries and last refresh timestamp
    GET /status
    """
    metadata = RefreshMetadata.query.first()
    
    if not metadata:
        return jsonify({
            "total_countries": 0,
            "last_refreshed_at": None
        }), 200
    
    return jsonify(metadata.to_dict()), 200


@app.route('/countries/image', methods=['GET'])
def get_summary_image():
    """
    Serve the generated summary image
    GET /countries/image
    """
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
    app.run(debug=True, host='0.0.0.0', port=port)
