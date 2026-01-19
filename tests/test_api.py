import pytest


def test_quiz_flow(client, sample_quiz_content):
    user_response = client.post(
        "/users",
        json={"username": "alice", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_response = client.post(
        "/quizzes",
        json={
            "user_id": user_id,
            "prompt": "Math and space",
            "quiz_content": sample_quiz_content,
        },
    )
    assert quiz_response.status_code == 201
    quiz_payload = quiz_response.json()
    quiz_id = quiz_payload["id"]

    list_response = client.get(f"/quizzes?user_id={user_id}")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == quiz_id

    take_response = client.get(f"/quizzes/{quiz_id}")
    assert take_response.status_code == 200
    public_questions = take_response.json()["quiz_public"]["questions"]
    assert "correct_option_key" not in public_questions[0]
    assert "explanation" not in public_questions[0]

    answer_map = {
        1: "B",
        2: "B",
        3: "A",
        4: "B",
        5: "B",
    }
    for question_index in range(1, 6):
        answer_response = client.post(
            f"/quizzes/{quiz_id}/answers",
            json={
                "question_index": question_index,
                "selected_option_key": answer_map[question_index],
            },
        )
        assert answer_response.status_code == 200
        payload = answer_response.json()
        expected_status = "completed" if question_index == 5 else "in_progress"
        assert payload["status"] == expected_status

    results_response = client.get(f"/quizzes/{quiz_id}/results")
    assert results_response.status_code == 200
    results = results_response.json()
    assert results["score"]["correct_count"] == 1
    assert results["score"]["total_questions"] == 5
    assert results["score"]["score_percent"] == 20.0


@pytest.mark.parametrize("question_count", [4, 6])
def test_quiz_rejects_invalid_question_count(
    client, question_count, build_quiz_content
):
    user_response = client.post(
        "/users",
        json={"username": f"user{question_count}", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_response = client.post(
        "/quizzes",
        json={
            "user_id": user_id,
            "prompt": "Invalid count",
            "quiz_content": build_quiz_content("Sample", question_count),
        },
    )
    assert quiz_response.status_code == 400
    assert quiz_response.json()["detail"] == "quiz_content must include exactly 5 questions"


def test_quiz_allows_five_questions(client, build_quiz_content):
    user_response = client.post(
        "/users",
        json={"username": "validuser", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_response = client.post(
        "/quizzes",
        json={
            "user_id": user_id,
            "prompt": "Valid count",
            "quiz_content": build_quiz_content("Valid", 5),
        },
    )
    assert quiz_response.status_code == 201


def test_placeholder_quiz_creation(client):
    user_response = client.post(
        "/users",
        json={"username": "placeholder", "password": "secret"},
    )
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]

    quiz_response = client.post(
        "/quizzes/placeholder",
        json={"user_id": user_id, "prompt": "Oceanography"},
    )
    assert quiz_response.status_code == 201
    quiz_payload = quiz_response.json()

    assert quiz_payload["prompt"] == "Oceanography"
    assert quiz_payload["status"] == "in_progress"
    assert quiz_payload["total_questions"] == 5
    assert len(quiz_payload["quiz_public"]["questions"]) == 5
    assert "correct_option_key" not in quiz_payload["quiz_public"]["questions"][0]

    list_response = client.get(f"/quizzes?user_id={user_id}")
    assert list_response.status_code == 200
    quiz_ids = {quiz["id"] for quiz in list_response.json()}
    assert quiz_payload["id"] in quiz_ids
