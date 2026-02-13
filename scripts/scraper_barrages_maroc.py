#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour vérifier que psycopg2 fonctionne
"""

print("=" * 60)
print("TEST PSYCOPG2")
print("=" * 60)

# Test 1: Import psycopg2
print("\n1. Testing psycopg2 import...")
try:
    import psycopg2
    print(f"✅ SUCCESS: psycopg2 imported! Version: {psycopg2.__version__}")
except ImportError as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Test 2: Import requests
print("\n2. Testing requests import...")
try:
    import requests
    print(f"✅ SUCCESS: requests imported! Version: {requests.__version__}")
except ImportError as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Test 3: Import beautifulsoup4
print("\n3. Testing beautifulsoup4 import...")
try:
    from bs4 import BeautifulSoup
    print("✅ SUCCESS: beautifulsoup4 imported!")
except ImportError as e:
    print(f"❌ FAILED: {e}")
    exit(1)

# Test 4: Test DATABASE_URL
print("\n4. Testing DATABASE_URL...")
import os
db_url = os.getenv('DATABASE_URL')
if db_url:
    print(f"✅ DATABASE_URL is set: {db_url[:30]}...")
else:
    print("⚠️  WARNING: DATABASE_URL is not set")

# Test 5: Create dummy JSON
print("\n5. Creating dummy barrages_data.json...")
import json
from datetime import datetime

dummy_data = {
    'date_extraction': datetime.now().isoformat(),
    'source': 'test',
    'nombre_barrages': 1,
    'barrages': [
        {
            'nom': 'Al Massira (TEST)',
            'bassin': 'Oum Er-Rbia',
            'capacite_totale': 2760,
            'volume_actuel': 1456,
            'taux_remplissage': 52.8,
            'date_maj': datetime.now().strftime('%Y-%m-%d'),
            'timestamp': datetime.now().isoformat()
        }
    ]
}

with open('barrages_data.json', 'w', encoding='utf-8') as f:
    json.dump(dummy_data, f, ensure_ascii=False, indent=2)

print("✅ SUCCESS: barrages_data.json created")

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
