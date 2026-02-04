# ⏰ CONFIGURATION RECALCUL RISQUE INONDATION (Toutes les 6h)

## 🎯 Stratégie

Le recalcul des zones à risque sera déclenché toutes les **6 heures** pour :
- Limiter consommation CPU (tier gratuit Supabase)
- Synchroniser avec mises à jour météo Open-Meteo
- Optimiser coûts cloud

**Horaires de recalcul :** 00h, 06h, 12h, 18h UTC

---

## ⚙️ OPTION 1: GitHub Actions (GRATUIT ⭐)

### Workflow `.github/workflows/recalcul_risque.yml`

```yaml
name: Recalcul Zones à Risque Inondation

on:
  schedule:
    # Toutes les 6 heures : 00h, 06h, 12h, 18h UTC
    - cron: '0 0,6,12,18 * * *'
  
  # Déclenchement manuel
  workflow_dispatch:

jobs:
  calculate-risk:
    runs-on: ubuntu-latest
    timeout-minutes: 30  # Timeout sécurité
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install -r requirements_risk.txt
      
      - name: Download DEM (cached)
        uses: actions/cache@v4
        id: dem-cache
        with:
          path: /tmp/dem_cache
          key: dem-maroc-srtm-30m-v1
      
      - name: Fetch latest weather data
        env:
          DATABASE_URL: ${{ secrets.SUPABASE_DATABASE_URL }}
        run: |
          python scripts/fetch_weather_forecasts.py
      
      - name: Calculate flood risk zones
        env:
          DATABASE_URL: ${{ secrets.SUPABASE_DATABASE_URL }}
          DEM_GEOTIFF_URL: ${{ secrets.DEM_GEOTIFF_URL }}
        run: |
          python scripts/calculate_flood_risk.py --update-db
      
      - name: Update risk scores
        env:
          DATABASE_URL: ${{ secrets.SUPABASE_DATABASE_URL }}
        run: |
          python scripts/update_risk_scores.py
      
      - name: Notification Discord (si erreur)
        if: failure()
        env:
          DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: |
          curl -X POST "$DISCORD_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d '{"content":"⚠️ Échec recalcul risque inondation"}'
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: risk-calculation-logs-${{ github.run_number }}
          path: logs/*.log
          retention-days: 7
```

---

## ⚙️ OPTION 2: Supabase Edge Functions (Deno)

### Fichier `supabase/functions/recalcul-risque/index.ts`

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  try {
    console.log('🔄 Début recalcul zones à risque')
    
    // Connexion Supabase
    const supabaseClient = createClient(
      Deno.env.get('SUPABASE_URL') ?? '',
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    )
    
    // 1. Récupérer prévisions météo récentes
    const { data: forecasts } = await supabaseClient
      .from('weather_forecasts')
      .select('*')
      .gte('forecast_time', new Date().toISOString())
      .lte('forecast_time', new Date(Date.now() + 24*60*60*1000).toISOString())
    
    // 2. Récupérer zones à analyser
    const { data: zones } = await supabaseClient
      .from('zones_analyse')
      .select('id, geom, province')
    
    // 3. Calculer scores de risque
    const updates = []
    for (const zone of zones) {
      const riskScore = await calculateRiskScore(zone, forecasts)
      updates.push({
        zone_id: zone.id,
        score: riskScore.score,
        niveau: riskScore.level,
        updated_at: new Date().toISOString()
      })
    }
    
    // 4. Mise à jour batch
    const { error } = await supabaseClient
      .from('zones_risque_inondation')
      .upsert(updates)
    
    if (error) throw error
    
    console.log(`✅ ${updates.length} zones mises à jour`)
    
    return new Response(
      JSON.stringify({ success: true, zones_updated: updates.length }),
      { headers: { "Content-Type": "application/json" } }
    )
    
  } catch (error) {
    console.error('❌ Erreur:', error)
    return new Response(
      JSON.stringify({ error: error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    )
  }
})

async function calculateRiskScore(zone: any, forecasts: any[]): Promise<any> {
  // Logique de calcul (simplifié pour exemple)
  const relevantForecast = forecasts.find(f => 
    // Logique géospatiale pour trouver prévision pertinente
    true
  )
  
  const precipitation = relevantForecast?.precipitation_24h || 0
  
  let score = 0
  if (zone.altitude_moyenne < 50) score += 40
  if (zone.distance_oued_min < 200) score += 35
  if (precipitation > 50) score += 25
  
  const level = score > 70 ? 'CRITIQUE' : 
                score > 40 ? 'ÉLEVÉ' : 
                score > 20 ? 'MODÉRÉ' : 'FAIBLE'
  
  return { score, level }
}
```

### Déclenchement via Supabase Cron (pg_cron)

```sql
-- Activer extension pg_cron (nécessite plan Pro Supabase)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Planifier exécution toutes les 6h
SELECT cron.schedule(
    'recalcul-risque-6h',
    '0 */6 * * *',  -- Toutes les 6h
    $$
    SELECT net.http_post(
        url := 'https://votre-projet.supabase.co/functions/v1/recalcul-risque',
        headers := '{"Authorization": "Bearer ' || current_setting('app.service_role_key') || '"}'::jsonb
    );
    $$
);

-- Vérifier tâches planifiées
SELECT * FROM cron.job;
```

**⚠️ ATTENTION:** pg_cron nécessite Supabase **Pro** ($25/mois)  
Pour le **tier gratuit**, utiliser **GitHub Actions** (Option 1)

---

## ⚙️ OPTION 3: Cron Job Serveur (VPS)

### Script Python `calculate_flood_risk.py`

```python
#!/usr/bin/env python3
"""
Script de recalcul des zones à risque d'inondation
À exécuter toutes les 6 heures via crontab
"""

import psycopg2
import requests
from datetime import datetime, timedelta
import logging
from flood_risk_analyzer import FloodRiskAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_weather_forecasts():
    """Récupère prévisions météo pour le Maroc"""
    logger.info("Fetching weather forecasts...")
    
    # Zones principales du Maroc
    cities = [
        {'name': 'Casablanca', 'lat': 33.5731, 'lon': -7.5898},
        {'name': 'Rabat', 'lat': 34.0209, 'lon': -6.8416},
        {'name': 'Marrakech', 'lat': 31.6295, 'lon': -7.9811},
        # ... ajouter autres villes
    ]
    
    forecasts = []
    for city in cities:
        url = f"https://api.open-meteo.com/v1/forecast"
        params = {
            'latitude': city['lat'],
            'longitude': city['lon'],
            'hourly': 'precipitation',
            'forecast_days': 1
        }
        
        response = requests.get(url, params=params)
        data = response.json()
        
        # Calculer total pluie 24h
        total_precip = sum(data['hourly']['precipitation'])
        
        forecasts.append({
            'city': city['name'],
            'lat': city['lat'],
            'lon': city['lon'],
            'precipitation_24h': total_precip
        })
    
    return forecasts

def update_risk_zones(db_conn, forecasts):
    """Mise à jour des scores de risque en base"""
    cursor = db_conn.cursor()
    
    # Récupérer zones à analyser
    cursor.execute("""
        SELECT id, ST_X(ST_Centroid(geom)) as lon, 
               ST_Y(ST_Centroid(geom)) as lat,
               altitude_moyenne, distance_oued_min
        FROM zones_risque_inondation
    """)
    
    zones = cursor.fetchall()
    logger.info(f"Analysing {len(zones)} zones...")
    
    analyzer = FloodRiskAnalyzer(DEM_URL)
    
    updates = []
    for zone in zones:
        zone_id, lon, lat, altitude, distance_oued = zone
        
        # Trouver prévision la plus proche
        nearest_forecast = min(
            forecasts,
            key=lambda f: ((f['lat']-lat)**2 + (f['lon']-lon)**2)**0.5
        )
        
        # Calculer score
        risk = analyzer.calculate_flood_risk_score(
            lon, lat,
            distance_oued or 1000,
            nearest_forecast['precipitation_24h']
        )
        
        if 'error' not in risk:
            updates.append((
                risk['score'],
                risk['risk_level'],
                datetime.now(),
                zone_id
            ))
    
    # Mise à jour batch
    cursor.executemany("""
        UPDATE zones_risque_inondation
        SET score_risque = %s,
            niveau_risque = %s,
            derniere_analyse = %s
        WHERE id = %s
    """, updates)
    
    db_conn.commit()
    logger.info(f"✅ {len(updates)} zones updated")

def main():
    logger.info("=== DÉBUT RECALCUL RISQUE ===")
    
    try:
        # Connexion base de données
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        
        # Récupération météo
        forecasts = fetch_weather_forecasts()
        
        # Calcul et mise à jour
        update_risk_zones(conn, forecasts)
        
        conn.close()
        logger.info("=== RECALCUL TERMINÉ ===")
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        raise

if __name__ == "__main__":
    import os
    DEM_URL = os.getenv('DEM_GEOTIFF_URL')
    main()
```

### Configuration Crontab

```bash
# Éditer crontab
crontab -e

# Ajouter ligne (exécution toutes les 6h)
0 */6 * * * cd /home/user/monitoring-hydrique && /usr/bin/python3 calculate_flood_risk.py >> /var/log/risk_calculation.log 2>&1

# Vérifier crontab
crontab -l
```

---

## 📊 MONITORING DES EXÉCUTIONS

### Table de logs en base

```sql
CREATE TABLE IF NOT EXISTS job_execution_logs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20),  -- 'success', 'failed', 'running'
    zones_updated INTEGER,
    error_message TEXT,
    execution_time_seconds INTEGER
);

CREATE INDEX idx_job_logs_name ON job_execution_logs(job_name, started_at DESC);
```

### Script de logging

```python
def log_execution(job_name, status, zones_updated=0, error=None):
    cursor.execute("""
        INSERT INTO job_execution_logs 
        (job_name, completed_at, status, zones_updated, error_message, execution_time_seconds)
        VALUES (%s, NOW(), %s, %s, %s, 
                EXTRACT(EPOCH FROM (NOW() - (SELECT MAX(started_at) FROM job_execution_logs WHERE job_name = %s))))
    """, (job_name, status, zones_updated, error, job_name))
```

---

## 📋 CHECKLIST CONFIGURATION

- [ ] GitHub Actions workflow créé (`.github/workflows/recalcul_risque.yml`)
- [ ] Secrets GitHub configurés (DATABASE_URL, DEM_URL)
- [ ] Script Python `calculate_flood_risk.py` testé localement
- [ ] Table `zones_risque_inondation` créée en base
- [ ] Cache DEM configuré (GitHub Actions cache)
- [ ] Notifications Discord/Slack configurées (optionnel)
- [ ] Logs d'exécution activés
- [ ] Timeout de 30min configuré (sécurité)

---

## 🎯 RECOMMANDATION MVP

**Pour le tier gratuit Supabase:** Utiliser **GitHub Actions** (Option 1)

**Avantages:**
- ✅ 100% gratuit
- ✅ Logs centralisés
- ✅ Notifications intégrées
- ✅ Facile à déboguer
- ✅ Pas de serveur à maintenir

**Évolution future:** Migrer vers Supabase Edge Functions (Option 2) si plan Pro
