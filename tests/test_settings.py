"""外观主题设置端点测试"""


def test_theme_default_is_system(client):
    resp = client.get("/settings/theme")
    assert resp.status_code == 200
    assert resp.json() == {"theme": "system"}


def test_theme_set_and_persist(client):
    assert client.put("/settings/theme", json={"value": "dark"}).json() == {
        "theme": "dark"
    }
    assert client.get("/settings/theme").json() == {"theme": "dark"}
    # 换回浅色再查，确认落库持久
    client.put("/settings/theme", json={"value": "light"})
    assert client.get("/settings/theme").json() == {"theme": "light"}


def test_theme_rejects_invalid(client):
    assert client.put("/settings/theme", json={"value": "blue"}).status_code == 400
    # 非法值不改现状
    assert client.get("/settings/theme").json() == {"theme": "system"}
