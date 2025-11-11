from app import app

def test_health_endpoint():
    client = app.test_client()
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.get_json().get('status') == 'ok'
    # Check some security headers exist
    assert 'X-Content-Type-Options' in resp.headers
    assert 'X-Frame-Options' in resp.headers
    assert 'Content-Security-Policy' in resp.headers