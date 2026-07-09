def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"


def test_create_and_get_product(client):
    resp = client.post("/products", json={
        "brand": "TestBrand",
        "name": "Test Whey",
        "category": "protein_powder",
        "notes": "test note",
        "source_url": "https://example.com/products/test-whey",
    })
    assert resp.status_code == 201
    product = resp.json()
    assert product["brand"] == "TestBrand"
    assert product["status"] == "active"
    assert len(product["sources"]) == 1
    assert product["sources"][0]["source_type"] == "manufacturer"

    fetched = client.get(f"/products/{product['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Test Whey"


def test_product_not_found(client):
    assert client.get("/products/9999").status_code == 404


def test_category_filter(client):
    client.post("/products", json={"brand": "A", "name": "Powder", "category": "protein_powder"})
    client.post("/products", json={"brand": "B", "name": "Bar", "category": "protein_bar"})
    bars = client.get("/products", params={"category": "protein_bar"}).json()
    assert len(bars) == 1
    assert bars[0]["brand"] == "B"


def test_add_source(client):
    product = client.post("/products", json={
        "brand": "C", "name": "Isolate", "category": "protein_powder",
    }).json()
    resp = client.post(f"/products/{product['id']}/sources", json={
        "source_type": "mock", "source_url": "mock://maxfit_whey_v1",
    })
    assert resp.status_code == 201
    assert resp.json()["source_url"] == "mock://maxfit_whey_v1"


def test_dashboard_stats_empty(client):
    stats = client.get("/dashboard/stats").json()
    assert stats["tracked_products"] == 0
    assert stats["failed_runs_this_week"] == 0
