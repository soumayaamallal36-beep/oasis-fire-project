import rasterio
import matplotlib.pyplot as plt
import os
from matplotlib.colors import ListedColormap

# ============================================
# CONFIGURATION
# ============================================
base_path = r'C:\Users\hp\Desktop\oasis_fire_project'
indices_path = os.path.join(base_path, 'data/processed/indices')
output_path = os.path.join(indices_path, 'png_couleur')
os.makedirs(output_path, exist_ok=True)

print("=" * 60)
print("🖼️ GÉNÉRATION DES IMAGES PNG COULEUR")
print("=" * 60)

# ============================================
# 1. NDVI (avant et après)
# ============================================
print("\n🌱 Génération NDVI...")

with rasterio.open(os.path.join(indices_path, 'ndvi_before.tif')) as src:
    ndvi_before = src.read(1)

with rasterio.open(os.path.join(indices_path, 'ndvi_after.tif')) as src:
    ndvi_after = src.read(1)

# NDVI avant
plt.figure(figsize=(10, 8))
im = plt.imshow(ndvi_before, cmap='RdYlGn', vmin=-1, vmax=1)
plt.colorbar(im, label='NDVI')
plt.title('NDVI avant incendie - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'ndvi_before.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ ndvi_before.png")

# NDVI après
plt.figure(figsize=(10, 8))
im = plt.imshow(ndvi_after, cmap='RdYlGn', vmin=-1, vmax=1)
plt.colorbar(im, label='NDVI')
plt.title('NDVI après incendie - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'ndvi_after.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ ndvi_after.png")

# ============================================
# 2. NBR (avant et après)
# ============================================
print("\n🔥 Génération NBR...")

with rasterio.open(os.path.join(indices_path, 'nbr_before.tif')) as src:
    nbr_before = src.read(1)

with rasterio.open(os.path.join(indices_path, 'nbr_after.tif')) as src:
    nbr_after = src.read(1)

# NBR avant
plt.figure(figsize=(10, 8))
im = plt.imshow(nbr_before, cmap='RdYlBu', vmin=-1, vmax=1)
plt.colorbar(im, label='NBR')
plt.title('NBR avant incendie - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'nbr_before.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ nbr_before.png")

# NBR après
plt.figure(figsize=(10, 8))
im = plt.imshow(nbr_after, cmap='RdYlBu', vmin=-1, vmax=1)
plt.colorbar(im, label='NBR')
plt.title('NBR après incendie - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'nbr_after.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ nbr_after.png")

# ============================================
# 3. dNBR (sévérité)
# ============================================
print("\n📊 Génération dNBR...")

with rasterio.open(os.path.join(indices_path, 'dnbr.tif')) as src:
    dnbr = src.read(1)

plt.figure(figsize=(10, 8))
im = plt.imshow(dnbr, cmap='RdYlBu_r', vmin=-0.5, vmax=1)
plt.colorbar(im, label='dNBR')
plt.title('dNBR - Sévérité de l\'incendie - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'dnbr.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ dnbr.png")

# ============================================
# 4. NDMI (humidité avant et après)
# ============================================
print("\n💧 Génération NDMI...")

with rasterio.open(os.path.join(indices_path, 'ndmi_before.tif')) as src:
    ndmi_before = src.read(1)

with rasterio.open(os.path.join(indices_path, 'ndmi_after.tif')) as src:
    ndmi_after = src.read(1)

# NDMI avant
plt.figure(figsize=(10, 8))
im = plt.imshow(ndmi_before, cmap='Blues', vmin=-1, vmax=1)
plt.colorbar(im, label='NDMI')
plt.title('NDMI avant incendie (humidité) - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'ndmi_before.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ ndmi_before.png")

# NDMI après
plt.figure(figsize=(10, 8))
im = plt.imshow(ndmi_after, cmap='Blues', vmin=-1, vmax=1)
plt.colorbar(im, label='NDMI')
plt.title('NDMI après incendie (humidité) - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'ndmi_after.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ ndmi_after.png")

# ============================================
# 5. Sévérité classifiée (couleurs personnalisées)
# ============================================
print("\n🏷️ Génération carte de sévérité...")

with rasterio.open(os.path.join(indices_path, 'severity_classified.tif')) as src:
    severity = src.read(1)

# Couleurs personnalisées pour les 5 classes
colors = ['green', 'lightgreen', 'yellow', 'orange', 'darkred']
cmap_severity = ListedColormap(colors)

plt.figure(figsize=(10, 8))
im = plt.imshow(severity, cmap=cmap_severity, vmin=0, vmax=4)
cbar = plt.colorbar(im, ticks=[0, 1, 2, 3, 4])
cbar.ax.set_yticklabels(['Non brûlé', 'Faible', 'Moyen', 'Fort', 'Très fort'])
plt.title('Classification de la sévérité - Agdez 2025')
plt.axis('off')
plt.savefig(os.path.join(output_path, 'severity_classified.png'), dpi=300, bbox_inches='tight')
plt.close()
print("   ✅ severity_classified.png")

# ============================================
# 6. RÉSUMÉ
# ============================================
print("\n" + "=" * 60)
print("✅ GÉNÉRATION TERMINÉE!")
print("=" * 60)
print(f"\n📁 Images sauvegardées dans: {output_path}")
print("\nListe des images générées:")
print("   🌱 ndvi_before.png")
print("   🌱 ndvi_after.png")
print("   🔥 nbr_before.png")
print("   🔥 nbr_after.png")
print("   📊 dnbr.png")
print("   💧 ndmi_before.png")
print("   💧 ndmi_after.png")
print("   🏷️ severity_classified.png")