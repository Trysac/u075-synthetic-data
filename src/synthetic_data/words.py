"""Bundled generic word lists.

The names are common given names and surnames in English and Spanish. Any resemblance to
real people is coincidental.
"""

from __future__ import annotations

FIRST_NAMES: tuple[str, ...] = tuple(
    dict.fromkeys(
        [
            "James",
            "Mary",
            "Robert",
            "Patricia",
            "John",
            "Jennifer",
            "Michael",
            "Linda",
            "William",
            "Elizabeth",
            "David",
            "Barbara",
            "Richard",
            "Susan",
            "Joseph",
            "Carlos",
            "María",
            "José",
            "Lucía",
            "Javier",
            "Carmen",
            "Miguel",
            "Isabel",
            "Antonio",
            "Marta",
            "Francisco",
            "Elena",
            "Pablo",
            "Sofía",
            "Diego",
        ]
    )
)

LAST_NAMES: tuple[str, ...] = tuple(
    dict.fromkeys(
        [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Miller",
            "Davis",
            "Wilson",
            "Taylor",
            "Anderson",
            "Thomas",
            "Moore",
            "Martin",
            "Clark",
            "Lewis",
            "García",
            "Rodríguez",
            "Martínez",
            "López",
            "González",
            "Pérez",
            "Sánchez",
            "Ramírez",
            "Torres",
            "Flores",
            "Rivera",
            "Gómez",
            "Díaz",
            "Cruz",
            "Morales",
        ]
    )
)
