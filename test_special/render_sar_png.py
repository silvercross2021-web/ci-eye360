import rasterio
import numpy as np
import matplotlib.pyplot as plt
import os

def render_tif_to_png(tif_path, png_path):
    if not os.path.exists(tif_path):
        print(f"Fichier inexistant : {tif_path}")
        return
        
    with rasterio.open(tif_path) as src:
        data = src.read(1)
        
        # Plage d'affichage typique pour 
        # Sentinel-1 VV (en Décibels) : -25 (noir) à +5 (blanc)
        vmin = -25.0
        vmax = 5.0
        
        # Clip les données pour un bel affichage
        data_clipped = np.clip(data, vmin, vmax)
        
        # Normalisation entre 0 et 1 pour l'affichage
        data_norm = (data_clipped - vmin) / (vmax - vmin)
        
        plt.figure(figsize=(10, 8))
        # cmap='gray' car le radar est par nature en noir et blanc (intensité de retour)
        plt.imshow(data_norm, cmap='gray')
        plt.colorbar(label='Rétrodiffusion VV (Normalisée de -25dB à +5dB)')
        titre = "Radar SAR VV : " + os.path.basename(tif_path)
        plt.title(titre)
        plt.axis('off')
        
        plt.savefig(png_path, bbox_inches='tight', dpi=150)
        plt.close()
        print(f"✅ Rendu sauvegardé dans : {png_path}")

if __name__ == '__main__':
    render_tif_to_png("test_special/outputs/SAR_VV_2024.tif", "test_special/outputs/SAR_VV_2024_visu.png")
    render_tif_to_png("test_special/outputs/SAR_VV_2025.tif", "test_special/outputs/SAR_VV_2025_visu.png")
