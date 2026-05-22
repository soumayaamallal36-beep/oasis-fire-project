# FireWatch Agdez

Plateforme IA de prédiction d'incendies de forêt pour la région Drâa-Tafilalet (Maroc).

## Architecture

```text
+-------------------+       +-------------------+       +-------------------+
|   Open-Meteo API  | ----> |  Data Collection  | <---- |   NASA FIRMS API  |
+-------------------+       +-------------------+       +-------------------+
                                      |
                                      v
                            +-------------------+
                            | Feature Engineer  |
                            +-------------------+
                                      |
                                      v
+-------------------+       +-------------------+
|  Dashboard HTML   | <---- |    FastAPI        |
+-------------------+       +-------------------+
                                      |
                                      v
                            +-------------------+
                            |  Alerts (Email/   |
                            |  Slack)           |
                            +-------------------+
```

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Configurer le fichier .env
```

## Usage

Démarrer l'API :
```bash
python src/api/main.py
```

Ouvrir le Dashboard :
Ouvrez le fichier `dashboard/index.html` dans un navigateur.

## Résultats Modèles

| Modèle | F1-Score | Accuracy |
|--------|----------|----------|
| StackingClassifier | 0.924 | 93.1% |
| VotingClassifier | 0.915 | 92.0% |
| XGBoost | 0.910 | 91.5% |

## License

MIT
