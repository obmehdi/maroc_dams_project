#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyse de risque d'inondation basée sur DEM (Modèle Numérique de Terrain)
Utilise Cloud Optimized GeoTIFF (COG) pour éviter stockage lourd en base
Auteur: Monitoring Hydrique Maroc
Date: 2026-02-04
"""

import rasterio
from rasterio.windows import from_bounds
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, box
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FloodRiskAnalyzer:
    """Classe pour analyser risque inondation via DEM"""
    
    def __init__(self, dem_url):
        """
        Args:
            dem_url: URL du fichier COG (Cloud Optimized GeoTIFF)
                     Ex: https://storage.googleapis.com/votre-bucket/maroc_srtm_30m.tif
        """
        self.dem_url = dem_url
        
    def get_elevation(self, lon, lat):
        """
        Récupère l'altitude d'un point depuis le COG
        Utilise VSI (Virtual System Interface) de GDAL pour lecture HTTP
        
        Args:
            lon: Longitude (ex: -7.5898)
            lat: Latitude (ex: 33.5731)
        
        Returns:
            float: Altitude en mètres
        """
        try:
            # Lecture du GeoTIFF distant via HTTP
            with rasterio.open(f'/vsicurl/{self.dem_url}') as src:
                # Conversion coordonnées -> index pixel
                row, col = src.index(lon, lat)
                
                # Lecture valeur pixel
                elevation = src.read(1, window=((row, row+1), (col, col+1)))[0, 0]
                
                # Gestion valeurs NoData
                if elevation == src.nodata:
                    return None
                
                return float(elevation)
                
        except Exception as e:
            logger.error(f"Erreur lecture DEM: {e}")
            return None
    
    def get_elevation_zone(self, bbox, resolution=30):
        """
        Récupère les altitudes d'une zone rectangulaire
        
        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            resolution: Résolution en mètres (défaut 30m SRTM)
        
        Returns:
            numpy.array: Matrice d'altitudes
        """
        try:
            with rasterio.open(f'/vsicurl/{self.dem_url}') as src:
                # Définir fenêtre de lecture
                window = from_bounds(*bbox, transform=src.transform)
                
                # Lecture des données
                elevation_data = src.read(1, window=window)
                
                # Remplacer NoData par NaN
                elevation_data = np.where(
                    elevation_data == src.nodata,
                    np.nan,
                    elevation_data
                )
                
                return elevation_data
                
        except Exception as e:
            logger.error(f"Erreur lecture zone DEM: {e}")
            return None
    
    def identify_low_zones(self, bbox, threshold=100):
        """
        Identifie les zones basses (< threshold mètres)
        
        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat)
            threshold: Altitude seuil en mètres (défaut 100m)
        
        Returns:
            dict: Statistiques zones basses
        """
        elevation_data = self.get_elevation_zone(bbox)
        
        if elevation_data is None:
            return None
        
        # Masque zones basses
        low_zones = elevation_data < threshold
        
        stats = {
            'total_pixels': elevation_data.size,
            'low_zone_pixels': np.sum(low_zones),
            'low_zone_percentage': (np.sum(low_zones) / elevation_data.size) * 100,
            'min_elevation': float(np.nanmin(elevation_data)),
            'max_elevation': float(np.nanmax(elevation_data)),
            'mean_elevation': float(np.nanmean(elevation_data))
        }
        
        logger.info(f"Zones basses (<{threshold}m): {stats['low_zone_percentage']:.2f}%")
        
        return stats
    
    def calculate_flood_risk_score(self, lon, lat, waterway_distance, precipitation_24h):
        """
        Calcule un score de risque d'inondation (0-100)
        
        Args:
            lon, lat: Coordonnées du point
            waterway_distance: Distance au plus proche oued (mètres)
            precipitation_24h: Pluies prévues sur 24h (mm)
        
        Returns:
            dict: Score et niveau de risque
        """
        # 1. Récupérer altitude
        elevation = self.get_elevation(lon, lat)
        
        if elevation is None:
            return {'error': 'Altitude non disponible'}
        
        # 2. Calcul du score
        score = 0
        details = {}
        
        # Facteur altitude (40 points max)
        if elevation < 50:
            altitude_score = 40
        elif elevation < 100:
            altitude_score = 30
        elif elevation < 200:
            altitude_score = 15
        else:
            altitude_score = 5
        
        score += altitude_score
        details['altitude_m'] = elevation
        details['altitude_score'] = altitude_score
        
        # Facteur proximité oued (35 points max)
        if waterway_distance < 100:
            distance_score = 35
        elif waterway_distance < 300:
            distance_score = 25
        elif waterway_distance < 500:
            distance_score = 15
        elif waterway_distance < 1000:
            distance_score = 5
        else:
            distance_score = 0
        
        score += distance_score
        details['distance_oued_m'] = waterway_distance
        details['distance_score'] = distance_score
        
        # Facteur précipitations (25 points max)
        if precipitation_24h > 80:
            rain_score = 25
        elif precipitation_24h > 50:
            rain_score = 20
        elif precipitation_24h > 30:
            rain_score = 12
        elif precipitation_24h > 10:
            rain_score = 5
        else:
            rain_score = 0
        
        score += rain_score
        details['pluie_24h_mm'] = precipitation_24h
        details['pluie_score'] = rain_score
        
        # Déterminer niveau de risque
        if score >= 70:
            risk_level = "CRITIQUE"
            color = "#D32F2F"  # Rouge
        elif score >= 40:
            risk_level = "ÉLEVÉ"
            color = "#F57C00"  # Orange
        elif score >= 20:
            risk_level = "MODÉRÉ"
            color = "#FBC02D"  # Jaune
        else:
            risk_level = "FAIBLE"
            color = "#388E3C"  # Vert
        
        return {
            'score': score,
            'risk_level': risk_level,
            'color': color,
            'details': details,
            'coordinates': {'lon': lon, 'lat': lat}
        }
    
    def analyze_populated_areas(self, buildings_geojson, bbox, precipitation_24h):
        """
        Analyse le risque pour les zones habitées
        
        Args:
            buildings_geojson: GeoDataFrame des bâtiments (OSM)
            bbox: Zone d'analyse
            precipitation_24h: Pluies prévues
        
        Returns:
            GeoDataFrame avec score de risque par bâtiment
        """
        results = []
        
        for idx, building in buildings_geojson.iterrows():
            centroid = building.geometry.centroid
            
            # Calculer distance au plus proche oued (à implémenter)
            # Pour le MVP, distance fictive
            waterway_distance = 500  # TODO: Calcul réel
            
            risk = self.calculate_flood_risk_score(
                centroid.x,
                centroid.y,
                waterway_distance,
                precipitation_24h
            )
            
            if 'error' not in risk:
                results.append({
                    'geometry': building.geometry,
                    'risk_score': risk['score'],
                    'risk_level': risk['risk_level'],
                    'elevation': risk['details']['altitude_m']
                })
        
        return gpd.GeoDataFrame(results, crs='EPSG:4326')


def example_usage():
    """Exemple d'utilisation"""
    
    # URL du COG (à remplacer par votre URL réelle)
    DEM_URL = "https://storage.googleapis.com/monitoring-hydrique/maroc_srtm_30m.tif"
    
    analyzer = FloodRiskAnalyzer(DEM_URL)
    
    # Exemple 1: Altitude d'un point (Casablanca)
    elevation = analyzer.get_elevation(-7.5898, 33.5731)
    print(f"Altitude Casablanca: {elevation}m")
    
    # Exemple 2: Score de risque
    risk = analyzer.calculate_flood_risk_score(
        lon=-7.5898,
        lat=33.5731,
        waterway_distance=200,  # 200m d'un oued
        precipitation_24h=65     # 65mm de pluie prévue
    )
    print(f"Risque inondation: {risk['risk_level']} (Score: {risk['score']})")
    
    # Exemple 3: Zones basses dans une région
    bbox = (-8.0, 33.0, -7.0, 34.0)  # Région Casablanca
    stats = analyzer.identify_low_zones(bbox, threshold=100)
    print(f"Zones <100m: {stats['low_zone_percentage']:.1f}%")


if __name__ == "__main__":
    example_usage()
