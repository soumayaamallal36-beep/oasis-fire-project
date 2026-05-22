def calculate_fire_risk(
    temperature,
    humidity,
    wind_speed,
    ndvi
):

    score = 0

    if temperature > 40:
        score += 3

    elif temperature > 35:
        score += 2

    if humidity < 15:
        score += 3

    elif humidity < 30:
        score += 2

    if wind_speed > 30:
        score += 3

    elif wind_speed > 20:
        score += 2

    if ndvi < 0.2:
        score += 3

    elif ndvi < 0.4:
        score += 2

    if score >= 10:
        return "Très élevé"

    elif score >= 7:
        return "Élevé"

    elif score >= 4:
        return "Moyen"

    return "Faible"