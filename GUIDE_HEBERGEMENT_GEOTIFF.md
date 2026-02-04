# 🗺️ GUIDE: Hébergement Gratuit de Fichiers GeoTIFF

## Solutions d'Hébergement Gratuites

### ✅ Option 1: Google Cloud Storage (RECOMMANDÉ)
**Tier Gratuit:**
- 5 GB de stockage
- 1 GB de transfert sortant/mois
- 5000 requêtes GET/mois

**Étapes:**
```bash
# 1. Installer gcloud CLI
curl https://sdk.cloud.google.com | bash

# 2. Créer bucket public
gsutil mb -c STANDARD -l europe-west1 gs://monitoring-hydrique-maroc

# 3. Convertir GeoTIFF en COG (Cloud Optimized)
gdal_translate \
  -co TILED=YES \
  -co COPY_SRC_OVERVIEWS=YES \
  -co COMPRESS=DEFLATE \
  maroc_srtm.tif maroc_srtm_cog.tif

# 4. Upload
gsutil cp maroc_srtm_cog.tif gs://monitoring-hydrique-maroc/

# 5. Rendre public
gsutil iam ch allUsers:objectViewer gs://monitoring-hydrique-maroc
```

**URL d'accès:**
```
https://storage.googleapis.com/monitoring-hydrique-maroc/maroc_srtm_cog.tif
```

---

### ✅ Option 2: GitHub Releases
**Limites:**
- Fichiers < 2 GB
- Bande passante illimitée
- Parfait pour COG statiques

**Étapes:**
```bash
# 1. Créer release dans GitHub
gh release create v1.0.0 \
  maroc_srtm_cog.tif \
  --title "DEM Maroc SRTM 30m" \
  --notes "Modèle Numérique de Terrain"

# 2. URL d'accès
https://github.com/username/repo/releases/download/v1.0.0/maroc_srtm_cog.tif
```

---

### ✅ Option 3: Cloudflare R2 (Nouveau)
**Tier Gratuit:**
- 10 GB stockage
- Transfert sortant ILLIMITÉ (gros avantage)
- 1 million requêtes/mois

**Avantages:**
- Pas de frais de sortie (vs AWS S3)
- Compatible S3 API
- CDN intégré

---

### ✅ Option 4: Azure Blob Storage
**Tier Gratuit (12 mois):**
- 5 GB stockage LRS
- 20,000 requêtes lecture

---

## 🛠️ Optimisation du GeoTIFF

### Conversion en COG (Obligatoire pour performance)
```bash
# Installation GDAL
sudo apt-get install gdal-bin

# Conversion avec pyramides (overviews)
gdal_translate \
  -co TILED=YES \
  -co BLOCKXSIZE=512 \
  -co BLOCKYSIZE=512 \
  -co COMPRESS=LZW \
  -co PREDICTOR=2 \
  -co NUM_THREADS=ALL_CPUS \
  input.tif output_cog.tif

# Ajout des pyramides (zoom rapide)
gdaladdo -r average output_cog.tif 2 4 8 16

# Validation COG
rio cogeo validate output_cog.tif
```

---

## 📦 Structure Recommandée

```
monitoring-hydrique-maroc/
├── dem/
│   ├── maroc_srtm_30m_cog.tif       # DEM complet (1-2 GB)
│   └── maroc_srtm_90m_cog.tif       # Version légère (200 MB)
├── waterways/
│   └── maroc_oueds.geojson          # Tracés oueds
└── administrative/
    └── maroc_provinces.geojson      # Limites administratives
```

---

## 🚀 Performance: Lecture Optimisée

### Avec rasterio (Python)
```python
import rasterio
from rasterio.windows import from_bounds

# Lecture zone spécifique (pas tout le fichier)
url = '/vsicurl/https://storage.googleapis.com/.../maroc_cog.tif'

with rasterio.open(url) as src:
    # Lire seulement 1km² autour d'un point
    bbox = (-7.59, 33.57, -7.58, 33.58)
    window = from_bounds(*bbox, transform=src.transform)
    data = src.read(1, window=window)
```

### Cache Local (Optionnel)
```python
# Télécharger une fois, réutiliser
import requests
import os

def get_cached_dem(url, cache_dir='/tmp/dem_cache'):
    os.makedirs(cache_dir, exist_ok=True)
    filename = url.split('/')[-1]
    local_path = f"{cache_dir}/{filename}"
    
    if not os.path.exists(local_path):
        print("Downloading DEM...")
        r = requests.get(url)
        with open(local_path, 'wb') as f:
            f.write(r.content)
    
    return local_path
```

---

## 💰 Coûts Estimés (si dépassement gratuit)

| Service | Stockage (10 GB) | Transfert (100 GB/mois) | Total/mois |
|---------|------------------|-------------------------|------------|
| **GCS** | $0.20 | $12.00 | **$12.20** |
| **R2** | $0.15 | **$0.00** | **$0.15** ⭐ |
| **S3** | $0.23 | $9.00 | **$9.23** |
| **Azure** | $0.18 | $8.70 | **$8.88** |

**Recommandation:** Cloudflare R2 pour production (transfert gratuit)

---

## 🔒 Sécurité

### Empêcher listing bucket
```bash
# Google Cloud Storage
gsutil iam ch -d allUsers:objectViewer gs://bucket-name
gsutil iam ch allUsers:objectViewer gs://bucket-name/public/*
```

### CORS (si frontend direct)
```json
[
  {
    "origin": ["https://votre-app.com"],
    "method": ["GET", "HEAD"],
    "responseHeader": ["Content-Type", "Range"],
    "maxAgeSeconds": 3600
  }
]
```

---

## 📊 Monitoring Utilisation

### Google Cloud
```bash
# Voir statistiques bucket
gsutil du -sh gs://monitoring-hydrique-maroc

# Logs accès
gcloud logging read "resource.type=gcs_bucket" --limit 100
```

---

## ✅ Checklist Déploiement

- [ ] GeoTIFF converti en COG
- [ ] Pyramides (overviews) générées
- [ ] Fichier validé (`rio cogeo validate`)
- [ ] Uploadé sur bucket public
- [ ] URL testée dans rasterio
- [ ] Cache navigateur configuré (Cache-Control: max-age=86400)
- [ ] Monitoring activé

---

## 🆘 Troubleshooting

**Erreur: "Not a valid Cloud Optimized GeoTIFF"**
→ Regénérer avec paramètres TILED=YES

**Lecture lente**
→ Vérifier overviews avec `gdalinfo file.tif`

**403 Forbidden**
→ Vérifier permissions bucket (allUsers:objectViewer)

---

**Pour le MVP:** Utiliser GitHub Releases (simple) puis migrer vers R2 en production.
