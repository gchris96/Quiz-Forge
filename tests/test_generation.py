from app.quiz_generation import ensure_prompt_coverage, scrape_web_page


def test_ensure_prompt_coverage_injects_prompt(build_quiz_content):
    quiz_content = build_quiz_content("Astronomy")
    quiz_content["title"] = "Sample Quiz"
    updated = ensure_prompt_coverage("Photosynthesis", quiz_content)

    title = updated["title"].lower()
    prompts = " ".join(q["prompt"] for q in updated["questions"]).lower()
    assert "photosynthesis" in title or "photosynthesis" in prompts


def test_generate_quiz_creates_quiz_and_returns_public(
    client, monkeypatch, build_quiz_content
):
    prompt = "Neural Networks"
    captured = {}

    def fake_generate(prompt_value):
        captured["prompt"] = prompt_value
        return build_quiz_content(prompt_value)

    monkeypatch.setattr("app.main.generate_quiz_content", fake_generate)

    user_response = client.post(
        "/users",
        json={"username": "generator", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_response = client.post(
        "/quizzes/generate",
        json={"user_id": user_id, "prompt": prompt},
    )
    assert quiz_response.status_code == 201
    payload = quiz_response.json()

    assert captured["prompt"] == prompt
    assert prompt in payload["quiz_public"]["title"]
    assert len(payload["quiz_public"]["questions"]) == 5
    assert "correct_option_key" not in payload["quiz_public"]["questions"][0]

    list_response = client.get(f"/quizzes?user_id={user_id}")
    assert list_response.status_code == 200
    quiz_ids = {quiz["id"] for quiz in list_response.json()}
    assert payload["id"] in quiz_ids


def test_quiz_rejects_invalid_option_count(client, build_quiz_content):
    user_response = client.post(
        "/users",
        json={"username": "options", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_content = build_quiz_content("Plants")
    quiz_content["questions"][0]["options"] = [
        {"key": "A", "text": "Option A"},
        {"key": "B", "text": "Option B"},
        {"key": "C", "text": "Option C"},
    ]

    quiz_response = client.post(
        "/quizzes",
        json={
            "user_id": user_id,
            "prompt": "Invalid options",
            "quiz_content": quiz_content,
        },
    )
    assert quiz_response.status_code == 400
    assert quiz_response.json()["detail"] == "each question must include 4 options"


def test_quiz_rejects_invalid_correct_option(client, build_quiz_content):
    user_response = client.post(
        "/users",
        json={"username": "correctkey", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_content = build_quiz_content("History")
    quiz_content["questions"][0]["correct_option_key"] = "E"

    quiz_response = client.post(
        "/quizzes",
        json={
            "user_id": user_id,
            "prompt": "Invalid correct key",
            "quiz_content": quiz_content,
        },
    )
    assert quiz_response.status_code == 400
    assert (
        quiz_response.json()["detail"]
        == "correct_option_key must match one of the option keys"
    )


def test_generate_quiz_rejects_long_prompt(client):
    user_response = client.post(
        "/users",
        json={"username": "promptlimit", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_response = client.post(
        "/quizzes/generate",
        json={"user_id": user_id, "prompt": "Ancient Rome Empire History"},
    )
    assert quiz_response.status_code == 400
    assert quiz_response.json()["detail"] == "prompt must be 1-3 words"


def test_scrape_web_page_handles_http_error(monkeypatch):
    from urllib.error import HTTPError

    def fake_urlopen(*args, **kwargs):
        raise HTTPError("http://example.com", 404, "Not Found", None, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    result = scrape_web_page("http://example.com")

    assert "Unable to fetch" in result
    assert "404" in result or "Not Found" in result
