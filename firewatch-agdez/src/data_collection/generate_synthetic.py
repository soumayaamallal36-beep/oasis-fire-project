"""
FireWatch Agdez - Générateur de données synthétiques
Génère un dataset réaliste de 5000 lignes pour Agdez.
"""
import os, logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SyntheticData")

def generate_synthetic_dataset(n_samples: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Génère un dataset synthétique réaliste pour la région d'Agdez."""
    np.random.seed(seed)
    records = []
    samples_per_season = n_samples // 4
    remainder = n_samples - samples_per_season * 4

    season_configs = [
        {"name":"summer","months":[6,7,8],"temp":(35,45),"hum":(5,20),"wind":(15,40),
         "ndvi":(0.05,0.15),"season":3,"risk_probs":[0.05,0.10,0.45,0.40],"n":samples_per_season+remainder},
        {"name":"spring","months":[3,4,5],"temp":(25,38),"hum":(20,45),"wind":(10,30),
         "ndvi":(0.15,0.35),"season":2,"risk_probs":[0.20,0.35,0.30,0.15],"n":samples_per_season},
        {"name":"autumn","months":[9,10,11],"temp":(20,35),"hum":(25,50),"wind":(10,25),
         "ndvi":(0.12,0.28),"season":4,"risk_probs":[0.30,0.35,0.25,0.10],"n":samples_per_season},
        {"name":"winter","months":[12,1,2],"temp":(5,20),"hum":(40,70),"wind":(5,20),
         "ndvi":(0.10,0.25),"season":1,"risk_probs":[0.60,0.25,0.10,0.05],"n":samples_per_season},
    ]

    for cfg in season_configs:
        n = cfg["n"]
        temp = np.random.uniform(*cfg["temp"], n)
        hum = np.random.uniform(*cfg["hum"], n)
        wind = np.random.uniform(*cfg["wind"], n)
        precip_base = np.random.exponential(2, n) if cfg["season"] != 3 else np.random.exponential(0.3, n)
        ndvi = np.random.uniform(*cfg["ndvi"], n)
        noise_std = 0.05
        temp += np.random.normal(0, np.mean(temp)*noise_std, n)
        hum += np.random.normal(0, np.mean(hum)*noise_std, n)
        wind += np.random.normal(0, np.mean(wind)*noise_std, n)
        hum = np.clip(hum, 1, 100)
        wind = np.clip(wind, 0, 60)
        temp = np.clip(temp, -5, 55)
        precip = np.clip(precip_base, 0, 50)
        ndvi = np.clip(ndvi, 0.02, 0.6)

        # Compute derived features
        import math
        fwi_vals, kbdi_vals = [], []
        prev_kbdi = 100.0
        for i in range(n):
            h = max(1, min(hum[i], 100))
            mo = 147.2*(101-h)/(59.5+h)
            if precip[i] > 0.5:
                rf = precip[i]-0.5
                mo = min(mo+42.5*rf*math.exp(-100/(251-mo))*(1-math.exp(-6.93/rf)), 250)
            ed = max(0.942*(h**0.679)+11*math.exp((h-100)/10)+0.18*(21.1-temp[i]), 0)
            m = ed+(mo-ed)*0.5 if mo > ed else mo
            ffmc = max(0, min(59.5*(250-m)/(147.2+m), 101))
            fw = math.exp(0.05039*wind[i])
            fm = 147.2*(101-ffmc)/(59.5+ffmc)
            sf = 19.115*math.exp(-0.1386*fm)*(1+fm**5.31/4.93e7)
            isi = 0.208*fw*sf
            rk = max(1.894*(temp[i]+1.1)*(100-h)*1e-4, 0) if temp[i] > -1.1 else 0
            dmc = max(rk*2, 0)
            bui = max(0.8*dmc+2, 0)
            fd = 0.626*bui**0.809+2 if bui > 0 else 0
            b = 0.1*isi*fd
            fwi = math.exp(2.72*(0.434*math.log(b))**0.647) if b > 1 else b
            fwi_vals.append(round(max(0, min(fwi, 150)), 2))
            tf = temp[i]*9/5+32
            dr = (800-prev_kbdi)*(0.001+0.01*max(tf-50,0))/(1+10.88*math.exp(-0.001736*30))
            prev_kbdi = max(0, min(prev_kbdi - max(precip[i]*0.0394-0.2,0)*100 + dr, 800))
            kbdi_vals.append(round(prev_kbdi, 2))

        spi = np.random.normal(-0.5 if cfg["season"]==3 else 0.3, 0.8, n)
        elevation = np.random.normal(1050, 150, n)
        slope = np.random.uniform(2, 18, n)
        aspect = np.random.uniform(0, 360, n)
        dist_forest = np.random.uniform(1, 40, n)
        prev_fires = np.random.poisson(2 if cfg["season"]==3 else 1, n)
        drought = np.array(kbdi_vals)/800*0.5 + (1-hum/100)*0.3 + temp/50*0.2
        risk = np.random.choice([0,1,2,3], n, p=cfg["risk_probs"])

        months = np.random.choice(cfg["months"], n)
        base_date = datetime(2023, 1, 1)
        dates = [base_date + timedelta(days=int(np.random.randint(0, 365))) for _ in range(n)]

        for i in range(n):
            records.append({
                "temperature": round(temp[i], 1),
                "humidity": round(hum[i], 1),
                "wind_speed": round(wind[i], 1),
                "precipitation": round(precip[i], 2),
                "ndvi": round(ndvi[i], 4),
                "fwi": fwi_vals[i],
                "kbdi": kbdi_vals[i],
                "spi_3m": round(spi[i], 2),
                "season": cfg["season"],
                "elevation": round(elevation[i], 1),
                "slope": round(slope[i], 1),
                "aspect": round(aspect[i], 1),
                "distance_to_forest": round(dist_forest[i], 2),
                "previous_fires_3y": int(prev_fires[i]),
                "drought_index": round(drought[i], 3),
                "fire_risk_level": int(risk[i]),
            })

    df = pd.DataFrame(records).sample(frac=1, random_state=seed).reset_index(drop=True)
    logger.info("Dataset synthétique généré: %d lignes x %d colonnes", len(df), len(df.columns))
    return df

if __name__ == "__main__":
    df = generate_synthetic_dataset(5000)
    os.makedirs("data/processed", exist_ok=True)
    df.to_csv("data/processed/features.csv", index=False)
    info = f"""Dataset synthétique FireWatch Agdez
Généré le: {datetime.now().isoformat()}
Échantillons: {len(df)}
Features: {list(df.columns)}
Distribution risque:
{df['fire_risk_level'].value_counts().sort_index().to_string()}
Stats:
{df.describe().round(2).to_string()}
"""
    with open("data/processed/features_synthetic_info.txt", "w", encoding="utf-8") as f:
        f.write(info)
    print(f"✅ Dataset sauvegardé: data/processed/features.csv ({len(df)} lignes)")
    print(df["fire_risk_level"].value_counts().sort_index())
