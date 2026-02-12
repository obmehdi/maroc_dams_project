#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de scraping des données des barrages marocains
Source: Ministère de l'Équipement et de l'Eau (MEE)
Auteur: Monitoring Hydrique Maroc
Date: 2026-02-04
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
import logging

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BarragesScraper:
    """Classe pour scraper les données des barrages marocains"""
    
    def __init__(self):
        self.base_url = "http://www.water.gov.ma"
        # URL exacte à ajuster selon le site réel
        self.barrages_url = f"{self.base_url}/barrages/situation-journaliere"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
        
    def fetch_page(self):
        """Récupère le contenu HTML de la page"""
        try:
            logger.info(f"Fetching data from {self.barrages_url}")
            response = self.session.get(
                self.barrages_url, 
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            response.encoding = 'utf-8'  # Support caractères arabes
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur lors de la récupération de la page: {e}")
            return None
    
    def parse_barrages_table(self, html):
        """Parse le tableau HTML des barrages"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Trouver le tableau principal
        # ATTENTION: Adapter les sélecteurs selon la structure réelle du site
        table = soup.find('table', {'class': 'table-barrages'}) or soup.find('table')
        
        if not table:
            logger.warning("Aucun tableau trouvé sur la page")
            return []
        
        barrages_data = []
        rows = table.find_all('tr')[1:]  # Skip header row
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 4:
                continue
            
            try:
                barrage = {
                    'nom': cells[0].get_text(strip=True),
                    'bassin': cells[1].get_text(strip=True),
                    'capacite_totale': self._parse_number(cells[2].get_text(strip=True)),
                    'volume_actuel': self._parse_number(cells[3].get_text(strip=True)),
                    'taux_remplissage': self._parse_percentage(cells[4].get_text(strip=True)),
                    'date_maj': datetime.now().strftime('%Y-%m-%d'),
                    'timestamp': datetime.now().isoformat()
                }
                
                # Calcul automatique si taux non fourni
                if barrage['taux_remplissage'] is None and barrage['capacite_totale']:
                    barrage['taux_remplissage'] = round(
                        (barrage['volume_actuel'] / barrage['capacite_totale']) * 100, 2
                    )
                
                barrages_data.append(barrage)
                logger.info(f"✓ Barrage parsé: {barrage['nom']} ({barrage['taux_remplissage']}%)")
                
            except Exception as e:
                logger.error(f"Erreur parsing ligne: {e}")
                continue
        
        return barrages_data
    
    def _parse_number(self, text):
        """Convertit un texte en nombre (gère espaces et virgules)"""
        try:
            # Nettoie: "2 760,50" -> 2760.50
            cleaned = text.replace(' ', '').replace(',', '.').replace('\xa0', '')
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    
    def _parse_percentage(self, text):
        """Convertit un pourcentage en nombre"""
        try:
            return float(text.replace('%', '').replace(',', '.').strip())
        except ValueError:
            return None
    
    def save_to_json(self, data, filepath='barrages_data.json'):
        """Sauvegarde les données en JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'date_extraction': datetime.now().isoformat(),
                    'source': self.barrages_url,
                    'nombre_barrages': len(data),
                    'barrages': data
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"✓ Données sauvegardées dans {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erreur sauvegarde JSON: {e}")
            return False
    
    def insert_to_postgres(self, data):
        """Insert data into PostgreSQL (Supabase)"""
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.error("DATABASE_URL non définie")
            return False
        
        try:
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            
            # Insertion dans table historique
            insert_query = """
                INSERT INTO historique_niveaux 
                (barrage_nom, bassin, capacite_totale, volume_actuel, 
                 taux_remplissage, date_mesure, timestamp)
                VALUES %s
                ON CONFLICT (barrage_nom, date_mesure) 
                DO UPDATE SET 
                    volume_actuel = EXCLUDED.volume_actuel,
                    taux_remplissage = EXCLUDED.taux_remplissage,
                    timestamp = EXCLUDED.timestamp
            """
            
            values = [
                (
                    d['nom'], 
                    d['bassin'], 
                    d['capacite_totale'],
                    d['volume_actuel'],
                    d['taux_remplissage'],
                    d['date_maj'],
                    d['timestamp']
                )
                for d in data
            ]
            
            execute_values(cursor, insert_query, values)
            conn.commit()
            
            logger.info(f"✓ {len(data)} barrages insérés dans PostgreSQL")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Erreur PostgreSQL: {e}")
            return False
    
    def run(self):
        """Exécution complète du scraping"""
        logger.info("=== DÉBUT SCRAPING BARRAGES MAROC ===")
        
        # 1. Récupération HTML
        html = self.fetch_page()
        if not html:
            logger.error("Impossible de récupérer la page")
            return False
        
        # 2. Parsing
        barrages = self.parse_barrages_table(html)
        if not barrages:
            logger.warning("Aucune donnée extraite")
            return False
        
        logger.info(f"✓ {len(barrages)} barrages extraits")
        
        # 3. Sauvegarde JSON
        self.save_to_json(barrages)
        
        # 4. Insertion PostgreSQL
        if os.getenv('DATABASE_URL'):
            self.insert_to_postgres(barrages)
        else:
            logger.warning("DATABASE_URL non définie, skip PostgreSQL")
        
        logger.info("=== SCRAPING TERMINÉ ===")
        return True


def main():
    """Point d'entrée principal"""
    scraper = BarragesScraper()
    success = scraper.run()
    
    if not success:
        exit(1)  # Code erreur pour GitHub Actions


if __name__ == "__main__":
    main()
