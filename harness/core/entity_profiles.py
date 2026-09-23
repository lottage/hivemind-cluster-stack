#!/usr/bin/env python3
"""
Entity Profiles & Grounded Memory Fabric for Humans and Pets.
Maintains structured profiles for Austin, Savannah, Kylo, and Luna.
Generates Valkey A-MEM atomic fact cards (< 35 tokens) and syncs to Qdrant companion_profile.
Includes extensible polling hooks for Home Assistant calendars and social/web data.
"""

import os
import json
import time
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

logger = logging.getLogger("Harness.EntityProfiles")

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "profiles"))
PROFILES_FILE = os.path.join(DATA_DIR, "entity_profiles.json")


class EntityProfileManager:
    def __init__(self, profiles_path: str = PROFILES_FILE):
        self.profiles_path = profiles_path
        self.profiles: Dict[str, Any] = self._load_profiles()
        self.polling_cache: Dict[str, Any] = {}

    def _load_profiles(self) -> Dict[str, Any]:
        if os.path.exists(self.profiles_path):
            try:
                with open(self.profiles_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load {self.profiles_path}: {e}")
        return {
            "people": [
                {
                    "id": "person-austin",
                    "name": "Austin",
                    "role": "Husband / Dad / Homelab Architect",
                    "relations": ["Husband to Savannah", "Dad", "Homeowner", "Creator/Operator"],
                    "gender": "male",
                    "ethnicity": "Caucasian",
                    "physical_traits": {
                        "hair": "Dark hair",
                        "eyes": "Green eyes",
                        "height": "~5'10\" - 6'0\"",
                        "build": "Athletic / average build"
                    },
                    "invariants": [
                        "Austin is the human operator and creator; never address him as an agent.",
                        "Austin is husband to Savannah and dad."
                    ]
                },
                {
                    "id": "person-savannah",
                    "name": "Savannah",
                    "role": "Wife / Mom / Trusted Resident",
                    "relations": ["Wife to Austin", "Mom", "Trusted Resident"],
                    "gender": "female",
                    "ethnicity": "Caucasian",
                    "physical_traits": {
                        "hair": "Darker hair (sometimes curly, sometimes straight)",
                        "eyes": "Blue eyes",
                        "height": "Petite ~5'2\""
                    },
                    "vehicles": ["Subaru Outback"],
                    "invariants": [
                        "Savannah is Austin's wife and mom.",
                        "Savannah has darker hair and blue eyes."
                    ]
                }
            ],
            "pets": [
                {
                    "id": "pet-kylo",
                    "name": "Kylo",
                    "species": "dog",
                    "breed": "Miniature Dachshund (Long-Haired)",
                    "gender": "male",
                    "physical_traits": {
                        "coat": "Long silky black coat with rich tan/brown markings above eyebrows, on paws, chest, and muzzle",
                        "build": "Elongated body, short legs"
                    },
                    "invariants": [
                        "Kylo is a DOG, NEVER a cat.",
                        "Kylo is a long-haired miniature dachshund with brown eyebrow markings."
                    ]
                },
                {
                    "id": "pet-luna",
                    "name": "Luna",
                    "species": "cat",
                    "breed": "Domestic Shorthair (Tuxedo)",
                    "gender": "female",
                    "physical_traits": {
                        "coat": "Black and white tuxedo pattern, white paws, white chest/belly, black mask"
                    },
                    "invariants": [
                        "Luna is a CAT, NEVER a dog.",
                        "Luna is a female tuxedo cat who claims the living room coffee table."
                    ]
                }
            ]
        }

    def save_profiles(self):
        os.makedirs(os.path.dirname(self.profiles_path), exist_ok=True)
        try:
            with open(self.profiles_path, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save {self.profiles_path}: {e}")

    def generate_amem_cards(self) -> List[Dict[str, Any]]:
        """
        Generates dense (< 35 tokens) atomic cards for Valkey A-MEM with is_core_memory=True.
        """
        cards = []

        # 1. Austin Fact Card
        austin = next((p for p in self.profiles.get("people", []) if p.get("name") == "Austin"), None)
        if austin:
            pt = austin.get("physical_traits", {})
            text = (
                f"Austin is the human operator, husband to Savannah, and dad. "
                f"Male, Caucasian, {pt.get('hair', 'dark hair')}, {pt.get('eyes', 'green eyes')}."
            )
            cards.append({
                "id": "profile_austin",
                "atom": text,
                "keywords": ["austin", "husband", "dad", "operator", "creator", "human", "green", "eyes", "hair"],
                "category": "identity",
                "is_core_memory": True
            })

        # 2. Savannah Fact Card
        savannah = next((p for p in self.profiles.get("people", []) if p.get("name") == "Savannah"), None)
        if savannah:
            pt = savannah.get("physical_traits", {})
            text = (
                f"Savannah is Austin's wife and mom. "
                f"Female, Caucasian, {pt.get('hair', 'darker hair')}, {pt.get('eyes', 'blue eyes')}, drives Subaru Outback."
            )
            cards.append({
                "id": "profile_savannah",
                "atom": text,
                "keywords": ["savannah", "wife", "mom", "blue", "eyes", "subaru", "outback", "hair"],
                "category": "identity",
                "is_core_memory": True
            })

        # 3. Kylo Pet Card (Canine Invariant)
        kylo = next((p for p in self.profiles.get("pets", []) if p.get("name") == "Kylo"), None)
        if kylo:
            pt = kylo.get("physical_traits", {})
            text = (
                f"Kylo is Austin's dog (Miniature Dachshund, male). "
                f"Long silky black-and-tan coat with brown eyebrow markings. Kylo is a DOG, NEVER a cat."
            )
            cards.append({
                "id": "profile_kylo",
                "atom": text,
                "keywords": ["kylo", "dog", "canine", "dachshund", "pet", "eyebrow", "animals"],
                "category": "pets",
                "is_core_memory": True
            })

        # 4. Luna Pet Card (Feline Invariant)
        luna = next((p for p in self.profiles.get("pets", []) if p.get("name") == "Luna"), None)
        if luna:
            pt = luna.get("physical_traits", {})
            text = (
                f"Luna is Austin's cat (Tuxedo, female). "
                f"Black and white coat, white paws, claims coffee table. Luna is a CAT, NEVER a dog."
            )
            cards.append({
                "id": "profile_luna",
                "atom": text,
                "keywords": ["luna", "cat", "feline", "tuxedo", "pet", "table", "animals"],
                "category": "pets",
                "is_core_memory": True
            })

        # 5. Combined Household Animals Grounding Card
        cards.append({
            "id": "core_household_animals",
            "atom": (
                "Austin has exactly two pets: Kylo is a dog (dachshund). Luna is a cat (tuxedo). "
                "Never call Kylo a cat or Luna a dog. Outside cameras track wild fauna (deer, foxes)."
            ),
            "keywords": ["pets", "animals", "kylo", "luna", "cat", "dog", "fauna", "wildlife"],
            "category": "pets",
            "is_core_memory": True
        })

        return cards

    def sync_to_valkey(self, amem_instance=None):
        """Syncs all generated atomic cards to Valkey A-MEM."""
        cards = self.generate_amem_cards()
        if amem_instance:
            for c in cards:
                amem_instance.store_atom(
                    atom_id=c["id"],
                    atom_text=c["atom"],
                    keywords=c["keywords"],
                    category=c["category"],
                    confidence=1.0,
                    is_core_memory=True
                )
            logger.info(f"⚡ Synced {len(cards)} profile cards to Valkey A-MEM.")
        return cards

    def sync_to_qdrant(self, qdrant_url: str = "http://192.168.1.112:6333", embedder_url: str = "http://192.168.1.105:8003/v1"):
        """Syncs full profile dossiers into Qdrant companion_profile collection."""
        try:
            points = []
            for person in self.profiles.get("people", []):
                content = (
                    f"### Person Profile: {person['name']}\n"
                    f"- Role: {person.get('role')}\n"
                    f"- Relations: {', '.join(person.get('relations', []))}\n"
                    f"- Gender: {person.get('gender')}, Ethnicity: {person.get('ethnicity')}\n"
                    f"- Physical Traits: {json.dumps(person.get('physical_traits', {}))}\n"
                    f"- Invariants: {'; '.join(person.get('invariants', []))}"
                )
                points.append({
                    "id": f"person-{person['name'].lower()}",
                    "content": content,
                    "title": f"Profile: {person['name']}",
                    "category": "people"
                })

            for pet in self.profiles.get("pets", []):
                content = (
                    f"### Pet Profile: {pet['name']} ({pet.get('species')})\n"
                    f"- Species: {pet.get('species').upper()}\n"
                    f"- Breed: {pet.get('breed')}\n"
                    f"- Gender: {pet.get('gender')}\n"
                    f"- Physical Traits: {json.dumps(pet.get('physical_traits', {}))}\n"
                    f"- Invariants: {'; '.join(pet.get('invariants', []))}"
                )
                points.append({
                    "id": f"pet-{pet['name'].lower()}",
                    "content": content,
                    "title": f"Pet Profile: {pet['name']}",
                    "category": "pets"
                })

            import uuid
            # Vectorize via Embedder
            for pt in points:
                req_emb = urllib.request.Request(
                    f"{embedder_url.rstrip('/')}/embeddings",
                    data=json.dumps({"input": pt["content"][:800], "model": "embedder"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req_emb, timeout=10) as resp:
                    emb = json.loads(resp.read().decode("utf-8"))["data"][0]["embedding"]

                point_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, pt["id"]))
                point_body = {
                    "points": [
                        {
                            "id": point_uuid,
                            "vector": emb,
                            "payload": {
                                "title": pt["title"],
                                "content": pt["content"],
                                "category": pt["category"],
                                "entity_id": pt["id"],
                                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                        }
                    ]
                }
                req_q = urllib.request.Request(
                    f"{qdrant_url.rstrip('/')}/collections/companion_profile/points",
                    data=json.dumps(point_body).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="PUT"
                )
                urllib.request.urlopen(req_q, timeout=10)
            logger.info(f"✔ Synced {len(points)} entity dossiers to Qdrant companion_profile.")
            return True
        except Exception as e:
            logger.warning(f"Failed to sync profiles to Qdrant: {e}")
            return False

    def poll_calendar_events(self, hass_url: str = "http://192.168.1.82:8123", token: str = "") -> Dict[str, Any]:
        """Polls current calendar events from Home Assistant."""
        results = {}
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for person in self.profiles.get("people", []):
            hook = person.get("polling_hooks", {}).get("ha_calendar", {})
            if hook.get("enabled") and hook.get("entity_id"):
                ent = hook["entity_id"]
                try:
                    url = f"{hass_url.rstrip('/')}/api/calendars/{ent}"
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        events = json.loads(resp.read().decode("utf-8"))
                        results[person["name"]] = events
                except Exception:
                    results[person["name"]] = []
        return results

    def get_grounded_entity_summary(self) -> str:
        """Returns concise, high-priority markdown text for system prompt injection."""
        lines = [
            "### [VERIFIED HOUSEHOLD RESIDENTS & PETS GROUND TRUTH]:",
            "- **Austin**: Male, Caucasian, dark hair, green eyes. Husband to Savannah, Dad. Operator & creator.",
            "- **Savannah**: Female, Caucasian, darker hair (curly/straight), blue eyes. Wife to Austin, Mom. Drives Subaru Outback.",
            "- **Kylo (Dog)**: Long-haired Miniature Dachshund (male). Silky black coat, rich tan/brown eyebrow markings. Kylo is a DOG, NEVER a cat.",
            "- **Luna (Cat)**: Domestic Shorthair Tuxedo cat (female). Black and white, white paws/chest. Claims coffee table. Luna is a CAT, NEVER a dog.",
            "- **CRITICAL INVARIANT**: Never confuse Kylo and Luna's species. They are two distinct animals: 1 dog and 1 cat."
        ]
        return "\n".join(lines)


# Singleton instance
entity_profiles = EntityProfileManager()
