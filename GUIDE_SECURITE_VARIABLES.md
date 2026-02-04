# 🔐 GUIDE: Configuration Sécurisée des Variables d'Environnement

## 🎯 Objectif
Protéger les API keys, mots de passe et secrets de l'application.

---

## 📦 DÉVELOPPEMENT LOCAL

### 1. Fichier `.env` (JAMAIS commité sur Git)

```bash
# ==============================================
# VARIABLES D'ENVIRONNEMENT - DÉVELOPPEMENT
# ==============================================

# ============ DATABASE (Supabase) ============
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# ============ CLOUD STORAGE (GeoTIFF) ============
DEM_GEOTIFF_URL=https://storage.googleapis.com/monitoring-hydrique/maroc_srtm_30m.tif
GOOGLE_CLOUD_PROJECT_ID=monitoring-hydrique-maroc
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# ============ APIS EXTERNES ============
OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1
USGS_EARTHQUAKE_API=https://earthquake.usgs.gov/fdsnws/event/1

# ============ SCRAPING ============
MEE_BARRAGES_URL=http://www.water.gov.ma/barrages
USER_AGENT=Mozilla/5.0 (compatible; MonitoringHydrique/1.0)

# ============ SÉCURITÉ ============
JWT_SECRET=votre-secret-ultra-securise-minimum-32-caracteres
RATE_LIMIT_SIGNALEMENTS=5  # Max signalements par IP/jour
SESSION_SECRET=autre-secret-pour-sessions

# ============ MONITORING (Optionnel) ============
SENTRY_DSN=https://xxxxx@sentry.io/xxxxx
LOG_LEVEL=DEBUG

# ============ NOTIFICATIONS (Optionnel) ============
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxxx
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxxxx
```

---

### 2. `.gitignore` (OBLIGATOIRE)

```gitignore
# Secrets
.env
.env.local
.env.*.local
*.pem
*.key
service-account.json

# Logs
*.log
logs/

# Cache
__pycache__/
*.pyc
.pytest_cache/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

### 3. Chargement en Python

```python
# config.py
import os
from dotenv import load_dotenv

# Charger .env
load_dotenv()

class Config:
    """Configuration centralisée de l'application"""
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')
    
    # Storage
    DEM_URL = os.getenv('DEM_GEOTIFF_URL')
    
    # Sécurité
    JWT_SECRET = os.getenv('JWT_SECRET')
    RATE_LIMIT = int(os.getenv('RATE_LIMIT_SIGNALEMENTS', 5))
    
    # Validation
    @classmethod
    def validate(cls):
        """Vérifie que toutes les variables obligatoires sont définies"""
        required = ['DATABASE_URL', 'SUPABASE_URL', 'JWT_SECRET']
        missing = [var for var in required if not getattr(cls, var)]
        
        if missing:
            raise EnvironmentError(
                f"Variables manquantes: {', '.join(missing)}"
            )
        
        return True

# Usage dans l'application
if __name__ == "__main__":
    Config.validate()
    print("✓ Configuration valide")
```

---

## ☁️ PRODUCTION (GitHub Actions)

### 1. GitHub Secrets

**Aller dans :** `Settings > Secrets and variables > Actions > New repository secret`

**Secrets à créer :**

| Nom | Valeur | Usage |
|-----|--------|-------|
| `SUPABASE_DATABASE_URL` | `postgresql://...` | Connexion base de données |
| `SUPABASE_URL` | `https://xxx.supabase.co` | API Supabase |
| `SUPABASE_SERVICE_KEY` | `eyJhbGci...` | Opérations admin |
| `DEM_GEOTIFF_URL` | `https://storage...` | Fichier DEM |
| `JWT_SECRET` | `secret-prod-32-chars` | Authentification |
| `SENTRY_DSN` | `https://...@sentry.io/...` | Monitoring erreurs |

---

### 2. Workflow GitHub Actions (Sécurisé)

```yaml
# .github/workflows/deploy.yml
name: Deploy Production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    env:
      # Charger depuis GitHub Secrets
      DATABASE_URL: ${{ secrets.SUPABASE_DATABASE_URL }}
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_KEY: ${{ secrets.SUPABASE_SERVICE_KEY }}
      DEM_GEOTIFF_URL: ${{ secrets.DEM_GEOTIFF_URL }}
      JWT_SECRET: ${{ secrets.JWT_SECRET }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Validate config
        run: python -c "from config import Config; Config.validate()"
      
      - name: Run scraping
        run: python scraper_barrages_maroc.py
      
      # JAMAIS logger les secrets
      - name: Deploy
        run: |
          echo "Deploying with DATABASE_URL=${DATABASE_URL:0:20}..." # Tronqué
```

---

## 🚀 PRODUCTION (Vercel / Netlify)

### Vercel

```bash
# CLI Vercel
vercel env add DATABASE_URL production
# Coller la valeur quand demandé

# Ou via interface web
# https://vercel.com/votre-projet/settings/environment-variables
```

### Netlify

```bash
# CLI Netlify
netlify env:set DATABASE_URL "postgresql://..."

# Ou fichier netlify.toml
[build.environment]
  NODE_VERSION = "18"

# Variables via UI uniquement
```

---

## 🔄 ROTATION DES SECRETS (Bonne pratique)

### Générer nouveau secret JWT
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Rotation Supabase Keys
1. Aller dans Supabase Dashboard > Settings > API
2. Cliquer sur "Regenerate" pour `service_role` key
3. Mettre à jour GitHub Secrets immédiatement
4. Redéployer l'application

**Fréquence recommandée :** Tous les 90 jours

---

## ⚠️ ERREURS FRÉQUENTES À ÉVITER

### ❌ Commit de secrets dans Git
```bash
# MAUVAIS - Visible dans l'historique Git
git add .env
git commit -m "Add config"

# BON - .env dans .gitignore
echo ".env" >> .gitignore
git add .gitignore
```

### ❌ Secrets en clair dans le code
```python
# MAUVAIS
DATABASE_URL = "postgresql://user:password@localhost/db"

# BON
DATABASE_URL = os.getenv('DATABASE_URL')
```

### ❌ Logs contenant des secrets
```python
# MAUVAIS
print(f"Connexion avec {DATABASE_URL}")

# BON
print(f"Connexion établie à {DATABASE_URL.split('@')[1]}")
```

---

## 🛡️ SÉCURITÉ AVANCÉE

### 1. Chiffrement des secrets en local (optionnel)

```bash
# Installation
pip install cryptography

# Script de chiffrement
python
>>> from cryptography.fernet import Fernet
>>> key = Fernet.generate_key()
>>> print(key.decode())  # Sauvegarder cette clé de manière sécurisée
```

```python
# encrypt_secrets.py
from cryptography.fernet import Fernet

def encrypt_secret(secret, key):
    f = Fernet(key)
    return f.encrypt(secret.encode()).decode()

def decrypt_secret(encrypted, key):
    f = Fernet(key)
    return f.decrypt(encrypted.encode()).decode()
```

---

### 2. Validation des URLs (prévention injection)

```python
from urllib.parse import urlparse

def validate_database_url(url):
    """Vérifie que l'URL est PostgreSQL valide"""
    parsed = urlparse(url)
    
    if parsed.scheme not in ['postgresql', 'postgres']:
        raise ValueError("URL doit commencer par postgresql://")
    
    if not parsed.netloc:
        raise ValueError("Host manquant dans DATABASE_URL")
    
    return True
```

---

### 3. Rate Limiting API (protection)

```python
from functools import wraps
from flask import request, abort
import redis

redis_client = redis.Redis(host='localhost', port=6379)

def rate_limit(max_calls=5, period=86400):  # 5 appels/jour
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            key = f"rate_limit:{ip}:{f.__name__}"
            
            calls = redis_client.get(key)
            if calls and int(calls) >= max_calls:
                abort(429, "Limite de requêtes atteinte")
            
            redis_client.incr(key)
            redis_client.expire(key, period)
            
            return f(*args, **kwargs)
        return wrapped
    return decorator
```

---

## 📋 CHECKLIST SÉCURITÉ

- [ ] `.env` dans `.gitignore`
- [ ] Secrets stockés dans GitHub Secrets
- [ ] Variables validées au démarrage (Config.validate())
- [ ] Logs ne révèlent JAMAIS de secrets
- [ ] Rate limiting activé sur endpoints publics
- [ ] HTTPS obligatoire en production
- [ ] JWT_SECRET minimum 32 caractères
- [ ] Rotation secrets tous les 90 jours
- [ ] Service account Google Cloud restreint
- [ ] Supabase RLS activé sur tables sensibles

---

## 🆘 EN CAS DE LEAK DE SECRET

1. **IMMÉDIATEMENT** : Révoquer le secret (Supabase/Google Cloud)
2. Générer nouveau secret
3. Mettre à jour GitHub Secrets
4. Redéployer toutes les instances
5. Auditer logs d'accès pour usage non autorisé
6. Notifier l'équipe si nécessaire

---

## 📚 Ressources

- [GitHub Secrets Best Practices](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Supabase Security](https://supabase.com/docs/guides/security)
- [OWASP Secret Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
