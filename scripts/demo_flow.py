from __future__ import annotations

import json

import httpx

BASE_URL = "http://localhost:8000/api/v1"


def main() -> None:
    with httpx.Client(timeout=30) as client:
        project = (
            client.post(
                f"{BASE_URL}/projects",
                json={"name": "India Launch Slate", "organization_name": "Demo Studio"},
            )
            .raise_for_status()
            .json()
        )
        title = (
            client.post(
                f"{BASE_URL}/projects/{project['id']}/titles",
                json={
                    "name": "Shadow Bloom",
                    "synopsis": (
                        "A teenage spirit guardian must protect her city while learning to trust "
                        "unlikely friends caught between humanity and an ancient supernatural war."
                    ),
                    "content_format": "anime_series",
                    "primary_genre": "fantasy",
                    "genres": ["fantasy", "action", "drama"],
                    "themes": ["friendship", "spirits", "coming of age"],
                    "source_material": "original",
                    "expected_release_period": "March 2027",
                    "target_platform": "OTT",
                    "target_languages": ["Hindi", "Tamil", "Telugu"],
                    "target_states": ["Maharashtra", "Karnataka", "Tamil Nadu"],
                    "marketing_budget": "medium",
                },
            )
            .raise_for_status()
            .json()
        )
        started = client.post(f"{BASE_URL}/titles/{title['id']}/analyses").raise_for_status().json()
        result = (
            client.get(f"{BASE_URL}/analyses/{started['analysis_id']}/result")
            .raise_for_status()
            .json()
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
