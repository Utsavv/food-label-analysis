"""End-to-end check-now flow using the mock scraper (fixture-backed sources)."""


def _create_demo_product(client, fixture: str = "mock://maxfit_whey_v1") -> int:
    product = client.post("/products", json={
        "brand": "MaxFit", "name": "Whey Gold", "category": "protein_powder",
    }).json()
    client.post(f"/products/{product['id']}/sources", json={
        "source_type": "mock", "source_url": fixture,
    })
    return product["id"]


def test_first_check_creates_version_without_comparison(client):
    product_id = _create_demo_product(client)
    result = client.post(f"/products/{product_id}/check-now").json()
    assert result["status"] == "success"
    assert result["new_version_created"] is True
    assert result["label_version_id"] is not None
    assert result["comparison_id"] is None

    versions = client.get(f"/products/{product_id}/label-versions").json()
    assert len(versions) == 1
    assert versions[0]["version_number"] == 1


def test_unchanged_label_creates_no_new_version(client):
    product_id = _create_demo_product(client)
    client.post(f"/products/{product_id}/check-now")
    result = client.post(f"/products/{product_id}/check-now").json()
    assert result["status"] == "no_change"
    assert result["new_version_created"] is False
    assert len(client.get(f"/products/{product_id}/label-versions").json()) == 1


def test_changed_label_creates_comparison_and_analyses(client, db_session):
    product_id = _create_demo_product(client)
    client.post(f"/products/{product_id}/check-now")

    # Simulate the manufacturer updating the label
    from app.models import ProductSource

    source = db_session.query(ProductSource).filter_by(product_id=product_id).first()
    source.source_url = "mock://maxfit_whey_v2"
    db_session.commit()

    result = client.post(f"/products/{product_id}/check-now").json()
    assert result["status"] == "success"
    assert result["new_version_created"] is True
    assert result["comparison_id"] is not None
    assert result["significance_score"] >= 80  # protein drop + sodium jump + sweetener

    comparison = client.get(f"/comparisons/{result['comparison_id']}").json()
    types = {i["type"] for i in comparison["diff_json"]["items"]}
    assert "nutrient_amount_changed" in types
    assert "ingredient_added" in types

    analysis_types = {a["analysis_type"] for a in comparison["analyses"]}
    assert analysis_types == {"change_analysis", "health_context"}
    for analysis in comparison["analyses"]:
        assert analysis["model_name"]
        assert analysis["prompt_version"] == "v1.0"
        assert analysis["plain_english_summary"]


def test_failed_scrape_is_recorded_visibly(client):
    product_id = _create_demo_product(client, fixture="mock://does_not_exist")
    result = client.post(f"/products/{product_id}/check-now").json()
    assert result["status"] == "failed"
    assert "not found" in result["message"].lower()

    runs = client.get("/runs", params={"status": "failed"}).json()
    assert len(runs) == 1
    assert runs[0]["error_message"]


def test_check_now_without_source_is_400(client):
    product = client.post("/products", json={
        "brand": "NoSource", "name": "Nothing", "category": "protein_powder",
    }).json()
    resp = client.post(f"/products/{product['id']}/check-now")
    assert resp.status_code == 400
