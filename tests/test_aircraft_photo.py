from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.api_aircraft_photo import _normalise_photo


def test_planespotters_photo_payload_is_normalised() -> None:
    result = _normalise_photo(
        {
            "photos": [
                {
                    "thumbnail": {
                        "src": "https://cdn.planespotters.net/photo/example.jpg"
                    },
                    "link": "https://www.planespotters.net/photo/example",
                    "photographer": "Example Photographer",
                }
            ]
        }
    )

    assert result == {
        "available": True,
        "image_url": "https://cdn.planespotters.net/photo/example.jpg",
        "link": "https://www.planespotters.net/photo/example",
        "photographer": "Example Photographer",
        "source": "Planespotters.net",
    }


def test_aircraft_photo_rejects_non_planespotters_image_hosts() -> None:
    result = _normalise_photo(
        {
            "photos": [
                {
                    "thumbnail": {"src": "https://example.com/not-trusted.jpg"},
                    "link": "https://www.planespotters.net/photo/example",
                }
            ]
        }
    )

    assert result == {"available": False}


def test_aircraft_photo_endpoint_fails_closed_for_invalid_hex() -> None:
    response = TestClient(app).get("/api/v1/aircraft/photo/not-a-hex")

    assert response.status_code == 200
    assert response.json() == {"available": False}
