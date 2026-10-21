def classify_load_level(hours_per_week):
    if hours_per_week < 20:
        return "low"
    if hours_per_week < 23:
        return "medium"
    return "high"
