from pathlib import Path


def test_signup_creates_user_and_returns_message(client):
    response = client.post(
        "/users",
        json={"username": "new_user", "password": "secret"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["message"] == "account created"
    assert payload["username"] == "new_user"
    assert payload["id"]

    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "new_user").one_or_none()
        assert user is not None
    finally:
        db.close()


def test_login_missing_user_prompts_account_creation(client):
    response = client.post(
        "/sessions",
        json={"username": "missing_user", "password": "secret"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "account not found. create an account."


def test_login_page_wires_app_js():
    root = Path(__file__).resolve().parents[1]
    index_html = root / "frontend" / "index.html"
    app_js = root / "frontend" / "app.js"

    index_content = index_html.read_text(encoding="utf-8")
    app_content = app_js.read_text(encoding="utf-8")

    assert 'data-page="login"' in index_content
    assert "data-login-form" in index_content
    assert "app.js" in index_content
    assert 'window.location.href = "home.html";' in app_content


def test_home_page_wires_quiz_list_and_refresh():
    root = Path(__file__).resolve().parents[1]
    home_html = root / "frontend" / "home.html"
    app_js = root / "frontend" / "app.js"

    home_content = home_html.read_text(encoding="utf-8")
    app_content = app_js.read_text(encoding="utf-8")

    assert 'data-page="home"' in home_content
    assert "data-quiz-list" in home_content
    assert "data-create-quiz" in home_content
    assert "data-refresh-quizzes" in home_content
    assert "/quizzes?user_id=" in app_content


def test_quiz_page_wires_buttons():
    root = Path(__file__).resolve().parents[1]
    quiz_html = root / "frontend" / "quiz.html"

    quiz_content = quiz_html.read_text(encoding="utf-8")

    assert 'data-page="quiz"' in quiz_content
    assert "data-submit-answer" in quiz_content
    assert "data-next-question" in quiz_content


def test_results_page_wires_buttons():
    root = Path(__file__).resolve().parents[1]
    results_html = root / "frontend" / "results.html"

    results_content = results_html.read_text(encoding="utf-8")

    assert 'data-page="results"' in results_content
    assert "data-back" in results_content
    assert "data-logout" in results_content
