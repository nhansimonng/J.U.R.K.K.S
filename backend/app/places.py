"""Optional Google Places adapter; existing local gyms work without a key."""
from uuid import NAMESPACE_URL, uuid5
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app import config, integrations
from app.models import Gym


def import_places(db, query, lat, lng, radius_km):
    if not config.GOOGLE_MAPS_API_KEY:
        return []
    headers = {"X-Goog-Api-Key": config.GOOGLE_MAPS_API_KEY,
               "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location"}
    circle = {"center": {"latitude": lat, "longitude": lng}, "radius": radius_km * 1000}
    if query:
        endpoint = "searchText"
        body = {"textQuery": query, "includedType": "gym", "strictTypeFiltering": True, "pageSize": 20}
        if lat is not None:
            body["locationBias"] = {"circle": circle}
    else:
        endpoint = "searchNearby"
        body = {"includedTypes": ["gym"], "maxResultCount": 20, "locationRestriction": {"circle": circle}}
    data = integrations.json_request("POST", f"https://places.googleapis.com/v1/places:{endpoint}",
                                     "Google Places", headers=headers, json=body)
    imported_ids = []
    for place in data.get("places", []):
        if not place.get("id") or not place.get("displayName", {}).get("text"):
            continue
        gym_id = uuid5(NAMESPACE_URL, "google-place:" + place["id"])
        gym = db.get(Gym, gym_id)
        if gym is None:
            gym = db.scalar(select(Gym).where(Gym.name == place["displayName"]["text"],
                                              Gym.address == place.get("formattedAddress")))
        if gym is None:
            try:
                with db.begin_nested():
                    gym = Gym(id=gym_id, name=place["displayName"]["text"])
                    db.add(gym)
                    db.flush()
            except IntegrityError:
                gym = db.get(Gym, gym_id)
                if gym is None:
                    raise
        gym.name = place["displayName"]["text"]
        gym.address = place.get("formattedAddress")
        gym.latitude = place.get("location", {}).get("latitude")
        gym.longitude = place.get("location", {}).get("longitude")
        imported_ids.append(gym.id)
    db.commit()
    return imported_ids
