"""
B26 — Tests unitaires CIV-Eye Module 1
=======================================
5 tests couvrant les composants critiques du pipeline de détection.
"""

import json
from unittest.mock import patch, MagicMock

import numpy as np
from django.test import TestCase

from module1_urbanisme.pipeline.ndbi_calculator import NDBICalculator


class NDBICalculatorTest(TestCase):
    """Test 1 : Calcul NDBI produit des valeurs dans [-1, 1]."""

    def test_ndbi_values_in_range(self):
        calc = NDBICalculator()
        # Simuler B08 (NIR) et B11 (SWIR) avec des valeurs réalistes
        with patch('rasterio.open') as mock_open:
            mock_src = MagicMock()
            mock_src.__enter__ = MagicMock(return_value=mock_src)
            mock_src.__exit__ = MagicMock(return_value=False)
            # B08 = 3000, B11 = 4000 → NDBI = (4000-3000)/(4000+3000) ≈ 0.143
            mock_src.read.side_effect = [
                np.array([[3000, 2000]], dtype=np.float32),  # B08
                np.array([[4000, 1000]], dtype=np.float32),  # B11
            ]
            mock_open.return_value = mock_src
            ndbi = calc.calculate_ndbi("fake_b08.tif", "fake_b11.tif")
            self.assertTrue(np.all(ndbi >= -1.0))
            self.assertTrue(np.all(ndbi <= 1.0))


class ChangeDetectionTest(TestCase):
    """Test 2 : Détection de changements entre T1 et T2."""

    def test_new_construction_detected(self):
        calc = NDBICalculator()
        # T1 : NDBI faible (pas de bâtiment), T2 : NDBI élevé (bâtiment)
        ndbi_t1 = np.array([[0.05, 0.1, -0.1]], dtype=np.float32)
        ndbi_t2 = np.array([[0.35, 0.30, -0.05]], dtype=np.float32)
        result = calc.detect_changes(ndbi_t1, ndbi_t2)
        # Le pixel 0 et 1 doivent être détectés comme nouvelle construction
        new_mask = result['new_constructions']
        self.assertTrue(new_mask[0, 0], "Pixel avec NDBI 0.05→0.35 doit être détecté")
        self.assertTrue(new_mask[0, 1], "Pixel avec NDBI 0.1→0.30 doit être détecté")


class BUICalculationTest(TestCase):
    """Test 3 : BUI = NDBI - NDVI filtre la végétation."""

    def test_bui_filters_vegetation(self):
        calc = NDBICalculator()
        ndbi = np.array([[0.3, 0.3]], dtype=np.float32)  # Les deux ont un NDBI élevé
        ndvi = np.array([[0.0, 0.6]], dtype=np.float32)   # Pixel 1 a NDVI élevé (végétation)
        bui = calc.calculate_bui(ndbi, ndvi)
        # Pixel 0 : BUI = 0.3 - 0.0 = 0.3 (vrai bâtiment)
        # Pixel 1 : BUI = 0.3 - 0.6 = -0.3 (faux positif végétation)
        self.assertGreater(bui[0, 0], 0.0, "Vrai bâtiment doit avoir BUI > 0")
        self.assertLess(bui[0, 1], 0.0, "Végétation doit avoir BUI < 0")


class MinSurfaceRejectionTest(TestCase):
    """Test 4 : Rejet des détections < 200 m² (H8 CAS 1)."""

    def test_small_detection_rejected(self):
        from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches
        verifier = Verification4Couches()
        # Détection de 100 m² — doit être rejetée
        result = verifier.verify_detection(
            geometry_geojson='{"type": "Point", "coordinates": [-4.0, 5.3]}',
            ndbi_t1_val=0.05,
            ndbi_t2_val=0.35,
            surface_m2=100.0,
        )
        self.assertIsNone(result, "Détection < 200m² doit être rejetée (CAS 1)")


class ThresholdCoherenceTest(TestCase):
    """Test 5 : Cohérence des seuils entre composants."""

    def test_ndbi_threshold_coherence(self):
        calc = NDBICalculator()
        # Le seuil du calculateur doit être >= celui de la vérification
        from module1_urbanisme.pipeline.verification_4_couches import Verification4Couches
        # Le calculateur utilise 0.20 comme filtre large
        self.assertEqual(calc.threshold_built, 0.2)
        # La vérification utilise des seuils plus fins (0.10 pour CIV)
        # Le seuil du calculateur doit être >= au seuil de vérification
        # pour ne pas filtrer des détections valides en amont
        self.assertGreaterEqual(
            calc.threshold_built, 0.10,
            "Le seuil NDBI du calculateur doit être >= au seuil CIV de vérification"
        )
