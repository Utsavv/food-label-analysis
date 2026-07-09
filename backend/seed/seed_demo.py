"""Seed demo data: two products, two label versions each, comparisons + AI analyses.

Runs the REAL pipeline over local fixture files (mock:// sources), so the demo
exercises scraping adapters, parsing, hashing, diffing, scoring and analysis —
no network or credentials needed.

Usage:  cd backend && python -m seed.seed_demo
"""
import logging

from sqlalchemy import select

import app.services.scraping.manufacturer_scraper  # noqa: F401 - registers adapters
from app.database import SessionLocal, init_db
from app.models import Product, ProductSource
from app.services.label_check import run_label_check

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed")

DEMO_PRODUCTS = [
    {
        "brand": "MaxFit",
        "name": "Whey Gold Premium Whey Protein (Chocolate)",
        "category": "protein_powder",
        "notes": "Demo product: sodium up, protein down, artificial sweetener added in v2.",
        "fixtures": ["mock://maxfit_whey_v1", "mock://maxfit_whey_v2"],
    },
    {
        "brand": "NutriCrunch",
        "name": "Peanut Protein Bar",
        "category": "protein_bar",
        "notes": "Demo product: allergen disclosures changed and 'no added sugar' claim removed in v2.",
        "fixtures": ["mock://nutricrunch_bar_v1", "mock://nutricrunch_bar_v2"],
    },
]


def seed() -> None:
    init_db()
    with SessionLocal() as db:
        for spec in DEMO_PRODUCTS:
            existing = db.scalars(
                select(Product).where(Product.brand == spec["brand"], Product.name == spec["name"])
            ).first()
            if existing:
                logger.info("Skipping %s %s (already seeded)", spec["brand"], spec["name"])
                continue

            product = Product(brand=spec["brand"], name=spec["name"],
                              category=spec["category"], notes=spec["notes"])
            db.add(product)
            db.flush()
            source = ProductSource(product_id=product.id, source_type="mock",
                                   source_url=spec["fixtures"][0])
            db.add(source)
            db.flush()

            # Walk the product through each fixture version via the real pipeline.
            for fixture_url in spec["fixtures"]:
                source.source_url = fixture_url
                db.flush()
                result = run_label_check(db, product.id, source_id=source.id, trigger="seed")
                logger.info("%s %s <- %s: %s", spec["brand"], spec["name"], fixture_url, result.message)

            db.commit()
            logger.info("Seeded %s %s", spec["brand"], spec["name"])

    logger.info("Demo seed complete. 'Run check now' will report no change (source points at latest fixture).")


if __name__ == "__main__":
    seed()
