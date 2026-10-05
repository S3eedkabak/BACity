"""Explainable completeness, not truth or invented data."""
def quality(event):
    weights = {'title': 10, 'description': 5, 'start_time': 20, 'end_time': 25,
               'venue_name': 10, 'coordinates': 10, 'category': 5, 'organizer_name': 5,
               'source_url': 5, 'image_url': 5}
    present = {key: bool(getattr(event, key, None)) for key in weights}
    present['coordinates'] = event.latitude is not None and event.longitude is not None
    present['category'] = event.category not in (None, '', 'Other')
    return {'score': sum(weight for key, weight in weights.items() if present[key]),
            'missing': [key for key in weights if not present[key]]}
