def classify_load_level(hours_per_week):
    if hours_per_week < 20:
        return "low"
    return "medium"
