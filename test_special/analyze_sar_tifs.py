import os
import rasterio
import numpy as np

def analyze_tif(filepath):
    print(f"\n==============================================")
    print(f"🔎 ANALYSE MINUTIEUSE DE : {filepath}")
    print(f"==============================================")
    
    if not os.path.exists(filepath):
        print("❌ ERREUR: Fichier introuvable.")
        return

    with rasterio.open(filepath) as src:
        data = src.read(1)
        profile = src.profile
        
        print(f"📐 1. MÉTADONNÉES SPATIALES :")
        print(f"   - Dimensions (Pixels) : {src.width} x {src.height} (Shape: {data.shape})")
        print(f"   - Système de projection (CRS) : {src.crs}")
        print(f"   - Bounding Box : {src.bounds}")
        print(f"   - Taille d'un pixel (Degrés) : {src.transform[0]:.6f} par {abs(src.transform[4]):.6f}")
        
        print(f"\n📊 2. VÉRIFICATION DES DONNÉES (Valeurs Radiométriques en dB) :")
        
        # Vérification des NaNs (pixels vides)
        nans = np.isnan(data)
        nan_count = np.sum(nans)
        pixel_count = data.size
        print(f"   - Pixels Totaux : {pixel_count}")
        print(f"   - Pixels Vides (NaN) : {nan_count} ({(nan_count/pixel_count)*100:.2f}%)")
        
        valid_data = data[~nans]
        if len(valid_data) == 0:
            print("   ❌ CRITIQUE : L'image est complètement vide (100% NaN).")
        else:
            vmin = valid_data.min()
            vmax = valid_data.max()
            vmean = valid_data.mean()
            vmedian = np.median(valid_data)
            
            print(f"   - Valeur Minimum : {vmin:.2f} dB")
            print(f"   - Valeur Maximum : {vmax:.2f} dB")
            print(f"   - Valeur Moyenne : {vmean:.2f} dB")
            print(f"   - Valeur Médiane : {vmedian:.2f} dB")
            
            # Analyse de la logique Radar (Sentinel-1 Sigma0)
            # Les valeurs typiques pour VV sont entre -25 dB (eau calme) et +5 dB (bâtiments denses)
            print("\n🧪 3. ANALYSE DE LA COHÉRENCE PHYSIQUE SAR :")
            if vmin < -40 or vmax > 30:
                print("   ⚠️ AVERTISSEMENT : Les valeurs dB semblent hors des limites habituelles de Sentinel-1 (-30 à +10 dB).")
                print("       (Cela peut arriver si des pixels bruités ne sont pas filtrés).")
            else:
                print("   ✅ COHÉRENT : Les valeurs sont dans l'échelle standard de rétrodiffusion radar (Sigma Nought dB).")
            
            # Nombre de pixels "très brillants" (Bâtiments potentiels, > 0 dB)
            high_backscatter = np.sum(valid_data > 0)
            print(f"   ℹ️ Nombre de pixels très brillants (> 0 dB, potentiels bâtiments) : {high_backscatter} ({(high_backscatter/len(valid_data))*100:.2f}%)")
            
            # Nombre de pixels "très sombres" (Eau potentielle, < -15 dB)
            low_backscatter = np.sum(valid_data < -15)
            print(f"   ℹ️ Nombre de pixels très sombres (< -15 dB, potentielle eau calme) : {low_backscatter} ({(low_backscatter/len(valid_data))*100:.2f}%)")

if __name__ == "__main__":
    analyze_tif("test_special/outputs/SAR_VV_2024.tif")
    analyze_tif("test_special/outputs/SAR_VV_2025.tif")
