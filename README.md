# 🌍 Country Currency & Exchange Rate API

A REST API that fetches country data and exchange rates, caches them in MySQL, and provides endpoints for filtering, sorting, and visualization.

---

## 📋 What You Need

- **Python 3.8+** ([Download](https://www.python.org/downloads/))
- **MySQL 8.0+** ([Download](https://dev.mysql.com/downloads/installer/))
- **Windows** (Mac/Linux commands are slightly different)

---

## 🚀 Setup Instructions (Windows)

### Step 1: Install MySQL

1. Download and install MySQL from https://dev.mysql.com/downloads/installer/
2. During installation, set a **root password**
3. Make sure MySQL service is running

**Verify MySQL is running:**
```bash
# Open Command Prompt as Administrator
net start MySQL80
```

---

### Step 2: Create the Database

**Open Command Prompt and run:**
```bash
mysql -u root -p
```
*Enter your MySQL password*

**Then run these SQL commands:**
```sql
CREATE DATABASE country_api CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
SHOW DATABASES;
exit;
```

You should see `country_api` in the database list.

---

### Step 3: Download/Create Project Files

**Create a project folder:**
```bash
mkdir C:\Projects\CountryAPI
cd C:\Projects\CountryAPI
```

**Create these 2 files:**

1. **`app.py`** - Copy the complete code from the artifact above
2. **`requirements.txt`** - Copy from the artifact above

---

### Step 4: Configure Database Password

**Open `app.py` in a text editor (Notepad, VS Code, etc.)**

**Find line ~15 and change the password:**
```python
DB_PASSWORD = "password"  # Change this to YOUR MySQL password
```

**Example:**
```python
DB_PASSWORD = "MySecretPass123"
```

**Save the file!**

---

### Step 5: Set Up Python Virtual Environment

**Open Command Prompt in your project folder:**
```bash
cd C:\Projects\CountryAPI

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate
```

You should see `(venv)` at the start of your command prompt.

---

### Step 6: Install Dependencies

```bash
pip install Flask==3.0.0
pip install flask-sqlalchemy==3.1.1
pip install mysql-connector-python==8.2.0
pip install requests==2.31.0
pip install Pillow==10.1.0
```

**Or install from requirements.txt:**
```bash
pip install -r requirements.txt
```

---

### Step 7: Create Cache Folder

```bash
mkdir cache
```

---

### Step 8: Run the Application

```bash
python app.py
```

**You should see:**
```
 * Running on http://127.0.0.1:5000
 * Running on http://0.0.0.0:5000
 * Restarting with stat
 * Debugger is active!
```

✅ **Your API is now running!**

**Keep this window open!**

---

## 🧪 Testing the API

### Method 1: Using Windows PowerShell (Recommended)

**Open a NEW PowerShell window** (keep python app.py running in the first)

**Navigate to your project:**
```powershell
cd C:\Projects\CountryAPI
```

**1. Refresh/Populate the Database (MUST DO FIRST!):**
```powershell
Invoke-RestMethod -Uri http://localhost:5000/countries/refresh -Method POST
```
*This takes 10-30 seconds. Wait for it to complete!*

**Expected output:**
```
message                              total_countries
-------                              ---------------
Countries refreshed successfully     250
```

**2. Check Status:**
```powershell
Invoke-RestMethod -Uri http://localhost:5000/status -Method GET
```

**3. Get All Countries:**
```powershell
Invoke-RestMethod -Uri http://localhost:5000/countries -Method GET
```

---

### Method 2: Using Browser

**After running the refresh command above, open these URLs in your browser:**

```
http://localhost:5000/status
http://localhost:5000/countries
http://localhost:5000/countries?region=Africa
http://localhost:5000/countries?currency=USD
http://localhost:5000/countries?sort=gdp_desc
http://localhost:5000/countries/Nigeria
http://localhost:5000/countries/image
```

---


## 📡 API Endpoints

| Method | Endpoint | Description | Example |
|--------|----------|-------------|---------|
| POST | `/countries/refresh` | Fetch and cache country data | `Invoke-RestMethod -Uri http://localhost:5000/countries/refresh -Method POST` |
| GET | `/countries` | Get all countries | `http://localhost:5000/countries` |
| GET | `/countries?region=Africa` | Filter by region | `http://localhost:5000/countries?region=Africa` |
| GET | `/countries?currency=USD` | Filter by currency | `http://localhost:5000/countries?currency=USD` |
| GET | `/countries?sort=gdp_desc` | Sort by GDP descending | `http://localhost:5000/countries?sort=gdp_desc` |
| GET | `/countries/{name}` | Get single country | `http://localhost:5000/countries/Nigeria` |
| DELETE | `/countries/{name}` | Delete a country | `Invoke-RestMethod -Uri http://localhost:5000/countries/Nigeria -Method DELETE` |
| GET | `/status` | Get total count and last refresh time | `http://localhost:5000/status` |
| GET | `/countries/image` | Download summary image | `http://localhost:5000/countries/image` |

---


## 📁 Project Structure

```
CountryAPI/
├── app.py              # Main application (all code here)
├── requirements.txt    # Python dependencies
├── cache/             # Generated summary images
│   └── summary.png
├── venv/              # Virtual environment (auto-created)
└── README.md          # This file
```

---


## 📚 Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [MySQL Documentation](https://dev.mysql.com/doc/)
- [REST API Tutorial](https://restfulapi.net/)

---
