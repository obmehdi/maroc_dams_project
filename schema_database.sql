-- ============================================================
-- SCHÉMA BASE DE DONNÉES POSTGIS - MONITORING HYDRIQUE MAROC
-- Plateforme: Supabase (PostgreSQL 15 + PostGIS 3.4)
-- Auteur: Monitoring Hydrique Maroc
-- Date: 2026-02-04
-- ============================================================

-- Activation extension PostGIS (si pas déjà fait)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- ============================================================
-- TABLE 1: BARRAGES (Données de référence)
-- ============================================================
CREATE TABLE IF NOT EXISTS barrages (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) NOT NULL UNIQUE,
    nom_ar VARCHAR(255),  -- Nom en arabe
    bassin VARCHAR(100) NOT NULL,  -- Ex: "Oum Er-Rbia", "Sebou"
    province VARCHAR(100),
    
    -- Données techniques
    capacite_totale DECIMAL(10, 2),  -- En millions de m³
    annee_mise_service INTEGER,
    hauteur_barrage DECIMAL(6, 2),   -- En mètres
    type_barrage VARCHAR(50),  -- Ex: "Terre", "Béton", "Enrochement"
    
    -- Géolocalisation (Point PostGIS)
    geom GEOMETRY(Point, 4326) NOT NULL,
    
    -- Métadonnées
    source_data VARCHAR(100) DEFAULT 'MEE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Contraintes
    CONSTRAINT check_capacite CHECK (capacite_totale > 0),
    CONSTRAINT check_hauteur CHECK (hauteur_barrage > 0)
);

-- Index spatial (OBLIGATOIRE pour performance)
CREATE INDEX idx_barrages_geom ON barrages USING GIST(geom);
CREATE INDEX idx_barrages_bassin ON barrages(bassin);

-- Trigger mise à jour automatique updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_barrages_updated_at
    BEFORE UPDATE ON barrages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- TABLE 2: HISTORIQUE NIVEAUX (Données quotidiennes)
-- ============================================================
CREATE TABLE IF NOT EXISTS historique_niveaux (
    id SERIAL PRIMARY KEY,
    barrage_id INTEGER REFERENCES barrages(id) ON DELETE CASCADE,
    barrage_nom VARCHAR(255) NOT NULL,  -- Dénormalisé pour requêtes rapides
    
    -- Données hydrologiques
    volume_actuel DECIMAL(10, 2) NOT NULL,      -- En millions de m³
    taux_remplissage DECIMAL(5, 2) NOT NULL,    -- En pourcentage (0-100)
    apports_journaliers DECIMAL(8, 2),          -- Apports en m³/s (si disponible)
    lachures_journalieres DECIMAL(8, 2),        -- Lâchures en m³/s
    
    -- Métadonnées temporelles
    date_mesure DATE NOT NULL,
    timestamp TIMESTAMP DEFAULT NOW(),
    source VARCHAR(50) DEFAULT 'scraping_MEE',
    
    -- Contraintes
    CONSTRAINT check_volume CHECK (volume_actuel >= 0),
    CONSTRAINT check_taux CHECK (taux_remplissage >= 0 AND taux_remplissage <= 100),
    CONSTRAINT unique_barrage_date UNIQUE(barrage_nom, date_mesure)
);

-- Index pour requêtes temporelles rapides
CREATE INDEX idx_historique_barrage_id ON historique_niveaux(barrage_id);
CREATE INDEX idx_historique_date ON historique_niveaux(date_mesure DESC);
CREATE INDEX idx_historique_barrage_date ON historique_niveaux(barrage_nom, date_mesure DESC);

-- ============================================================
-- TABLE 3: OUEDS (Cours d'eau)
-- ============================================================
CREATE TABLE IF NOT EXISTS oueds (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    nom_ar VARCHAR(255),
    bassin VARCHAR(100),
    
    -- Type et classification
    type VARCHAR(50) DEFAULT 'stream',  -- 'river', 'stream', 'wadi'
    ordre_strahler INTEGER,  -- Classification hydrologique
    longueur_km DECIMAL(8, 2),
    
    -- Géométrie (LineString)
    geom GEOMETRY(LineString, 4326) NOT NULL,
    
    -- Risque
    risque_crue VARCHAR(20) DEFAULT 'non_evalué',  -- 'faible', 'moyen', 'élevé'
    
    -- Métadonnées
    source_data VARCHAR(100) DEFAULT 'OSM',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_oueds_geom ON oueds USING GIST(geom);
CREATE INDEX idx_oueds_bassin ON oueds(bassin);

-- ============================================================
-- TABLE 4: SIGNALEMENTS CITOYENS
-- ============================================================
CREATE TABLE IF NOT EXISTS signalements (
    id SERIAL PRIMARY KEY,
    
    -- Localisation
    geom GEOMETRY(Point, 4326) NOT NULL,
    province VARCHAR(100),
    ville VARCHAR(100),
    
    -- Type de danger
    type_danger VARCHAR(50) NOT NULL,
    -- 'inondation', 'incendie', 'route_coupee', 'eboulement', 'autre'
    
    -- Contenu
    description TEXT,
    photo_url TEXT,  -- URL Supabase Storage
    
    -- Validation communautaire
    validations_positives INTEGER DEFAULT 0,
    validations_negatives INTEGER DEFAULT 0,
    statut VARCHAR(20) DEFAULT 'en_attente',  -- 'validé', 'rejeté', 'expiré'
    
    -- Métadonnées
    user_ip VARCHAR(45),  -- IPv4 ou IPv6
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '24 hours',
    
    -- Contraintes
    CONSTRAINT check_type_danger CHECK (
        type_danger IN ('inondation', 'incendie', 'route_coupee', 'eboulement', 'autre')
    )
);

CREATE INDEX idx_signalements_geom ON signalements USING GIST(geom);
CREATE INDEX idx_signalements_type ON signalements(type_danger);
CREATE INDEX idx_signalements_created ON signalements(created_at DESC);
CREATE INDEX idx_signalements_expires ON signalements(expires_at);

-- Fonction auto-nettoyage signalements expirés
CREATE OR REPLACE FUNCTION cleanup_expired_signalements()
RETURNS void AS $$
BEGIN
    UPDATE signalements
    SET statut = 'expiré'
    WHERE expires_at < NOW() AND statut = 'en_attente';
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TABLE 5: ALERTES MÉTÉO (Historique)
-- ============================================================
CREATE TABLE IF NOT EXISTS alertes_meteo (
    id SERIAL PRIMARY KEY,
    
    -- Zone affectée
    region VARCHAR(100),
    provinces TEXT[],  -- Array de provinces
    bbox GEOMETRY(Polygon, 4326),  -- Zone géographique
    
    -- Type et sévérité
    type_alerte VARCHAR(50) NOT NULL,  -- 'pluie', 'vent', 'chaleur', 'froid'
    severite VARCHAR(20) NOT NULL,     -- 'faible', 'modérée', 'élevée', 'critique'
    
    -- Données météo
    valeur DECIMAL(8, 2),  -- Ex: 75mm de pluie
    unite VARCHAR(20),     -- 'mm', 'km/h', '°C'
    
    -- Temporalité
    debut_prevision TIMESTAMP NOT NULL,
    fin_prevision TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Statut
    active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_alertes_region ON alertes_meteo(region);
CREATE INDEX idx_alertes_severite ON alertes_meteo(severite);
CREATE INDEX idx_alertes_active ON alertes_meteo(active, debut_prevision);

-- ============================================================
-- TABLE 6: ZONES À RISQUE INONDATION (Pré-calculées)
-- ============================================================
CREATE TABLE IF NOT EXISTS zones_risque_inondation (
    id SERIAL PRIMARY KEY,
    
    -- Identification zone
    nom VARCHAR(255),
    province VARCHAR(100),
    commune VARCHAR(100),
    
    -- Géométrie zone à risque
    geom GEOMETRY(Polygon, 4326) NOT NULL,
    
    -- Analyse risque
    score_risque INTEGER CHECK (score_risque BETWEEN 0 AND 100),
    niveau_risque VARCHAR(20),  -- 'FAIBLE', 'MODÉRÉ', 'ÉLEVÉ', 'CRITIQUE'
    
    -- Facteurs contributifs
    altitude_moyenne DECIMAL(6, 2),
    distance_oued_min DECIMAL(8, 2),  -- En mètres
    population_estimee INTEGER,
    nb_batiments INTEGER,
    
    -- Métadonnées
    derniere_analyse TIMESTAMP DEFAULT NOW(),
    source_calcul VARCHAR(100) DEFAULT 'DEM_SRTM_30m'
);

CREATE INDEX idx_zones_risque_geom ON zones_risque_inondation USING GIST(geom);
CREATE INDEX idx_zones_risque_niveau ON zones_risque_inondation(niveau_risque);

-- ============================================================
-- VUES UTILES
-- ============================================================

-- Vue: Derniers niveaux des barrages
CREATE OR REPLACE VIEW v_barrages_dernier_niveau AS
SELECT 
    b.id,
    b.nom,
    b.bassin,
    b.capacite_totale,
    ST_X(b.geom) AS longitude,
    ST_Y(b.geom) AS latitude,
    h.volume_actuel,
    h.taux_remplissage,
    h.date_mesure,
    -- Comparaison année précédente
    LAG(h.taux_remplissage, 365) OVER (
        PARTITION BY b.id ORDER BY h.date_mesure
    ) AS taux_annee_precedente
FROM barrages b
LEFT JOIN LATERAL (
    SELECT volume_actuel, taux_remplissage, date_mesure
    FROM historique_niveaux
    WHERE barrage_id = b.id
    ORDER BY date_mesure DESC
    LIMIT 1
) h ON TRUE;

-- Vue: Signalements actifs géolocalisés
CREATE OR REPLACE VIEW v_signalements_actifs AS
SELECT 
    id,
    type_danger,
    description,
    ST_X(geom) AS longitude,
    ST_Y(geom) AS latitude,
    validations_positives - validations_negatives AS score_validation,
    EXTRACT(EPOCH FROM (NOW() - created_at))/3600 AS heures_depuis_creation,
    statut
FROM signalements
WHERE statut = 'en_attente' 
  AND expires_at > NOW()
ORDER BY created_at DESC;

-- ============================================================
-- FONCTIONS UTILES
-- ============================================================

-- Fonction: Trouver barrages dans un rayon
CREATE OR REPLACE FUNCTION barrages_nearby(
    lat DECIMAL,
    lon DECIMAL,
    rayon_km DECIMAL DEFAULT 50
)
RETURNS TABLE (
    nom VARCHAR,
    distance_km DECIMAL,
    taux_remplissage DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        b.nom,
        ROUND(
            ST_Distance(
                b.geom::geography,
                ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
            ) / 1000,
            2
        ) AS distance_km,
        h.taux_remplissage
    FROM barrages b
    LEFT JOIN LATERAL (
        SELECT taux_remplissage
        FROM historique_niveaux
        WHERE barrage_id = b.id
        ORDER BY date_mesure DESC
        LIMIT 1
    ) h ON TRUE
    WHERE ST_DWithin(
        b.geom::geography,
        ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography,
        rayon_km * 1000
    )
    ORDER BY distance_km;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- ROW LEVEL SECURITY (RLS) - Supabase
-- ============================================================

-- Activer RLS sur tables sensibles
ALTER TABLE signalements ENABLE ROW LEVEL SECURITY;
ALTER TABLE alertes_meteo ENABLE ROW LEVEL SECURITY;

-- Politique: Tout le monde peut lire les signalements
CREATE POLICY "Signalements publics en lecture"
    ON signalements FOR SELECT
    USING (true);

-- Politique: Création limitée par IP (géré côté application)
CREATE POLICY "Création signalements limitée"
    ON signalements FOR INSERT
    WITH CHECK (true);  -- Logique anti-spam dans application

-- ============================================================
-- DONNÉES INITIALES (Exemples)
-- ============================================================

-- Insertion barrages principaux (à compléter)
INSERT INTO barrages (nom, nom_ar, bassin, capacite_totale, geom) VALUES
('Al Massira', 'المسيرة', 'Oum Er-Rbia', 2760, ST_SetSRID(ST_MakePoint(-8.2667, 32.4833), 4326)),
('Bin El Ouidane', 'بين الويدان', 'Oum Er-Rbia', 1460, ST_SetSRID(ST_MakePoint(-6.5833, 32.1167), 4326)),
('Youssef Ben Tachfine', 'يوسف بن تاشفين', 'Souss-Massa', 304, ST_SetSRID(ST_MakePoint(-8.5667, 30.5833), 4326)),
('Hassan II', 'الحسن الثاني', 'Bouregreg', 356, ST_SetSRID(ST_MakePoint(-6.7333, 33.6833), 4326))
ON CONFLICT (nom) DO NOTHING;

-- ============================================================
-- MAINTENANCE
-- ============================================================

-- Nettoyage quotidien automatique (via pg_cron ou Supabase Edge Function)
-- SELECT cleanup_expired_signalements();

-- Vacuum régulier
-- VACUUM ANALYZE historique_niveaux;
-- VACUUM ANALYZE signalements;

COMMENT ON TABLE barrages IS 'Données de référence des barrages marocains';
COMMENT ON TABLE historique_niveaux IS 'Historique quotidien des niveaux d eau';
COMMENT ON TABLE oueds IS 'Tracés des cours d eau (LineString)';
COMMENT ON TABLE signalements IS 'Signalements citoyens géolocalisés';
COMMENT ON TABLE zones_risque_inondation IS 'Zones pré-calculées à risque d inondation';
