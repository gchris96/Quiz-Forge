const STORAGE_KEY = "quizForge";
const API_BASE = "http://localhost:8000";

const loadState = () => {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return {
      user: null,
      currentQuizId: null,
      currentQuizPublic: null,
      currentQuizPrompt: null,
      currentIndex: 0,
      currentAnswers: [],
    };
  }
  try {
    return JSON.parse(raw);
  } catch (error) {
    return {
      user: null,
      currentQuizId: null,
      currentQuizPublic: null,
      currentQuizPrompt: null,
      currentIndex: 0,
      currentAnswers: [],
    };
  }
};

const saveState = (state) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

const updateState = (updates) => {
  const state = loadState();
  const next = { ...state, ...updates };
  saveState(next);
  return next;
};

const clearSession = () => {
  saveState({
    user: null,
    currentQuizId: null,
    currentQuizPublic: null,
    currentQuizPrompt: null,
    currentIndex: 0,
    currentAnswers: [],
  });
};

const setActiveUser = (user) => {
  updateState({ user });
};

const requireUser = () => {
  const state = loadState();
  if (!state.user) {
    window.location.href = "index.html";
  }
  return state;
};

const apiRequest = async (path, options = {}) => {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const config = { ...options, headers };
  if (config.body && typeof config.body !== "string") {
    config.body = JSON.stringify(config.body);
  }
  const response = await fetch(`${API_BASE}${path}`, config);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        message = payload.detail;
      }
    } catch (error) {
      // Ignore JSON parsing errors.
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
};

const renderFormError = (form, message) => {
  let error = form.querySelector("[data-form-error]");
  if (!error) {
    error = document.createElement("p");
    error.dataset.formError = "true";
    error.className = "hint";
    form.prepend(error);
  }
  error.textContent = message;
};

const initLogin = () => {
  const form = document.querySelector("[data-login-form]");
  if (!form) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = form.querySelector("input[name='username']").value.trim();
    const password = form.querySelector("input[name='password']").value;
    if (!username || !password) {
      renderFormError(form, "Incorrect username or password");
      return;
    }
    try {
      const payload = await apiRequest("/sessions", {
        method: "POST",
        body: { username, password },
      });
      setActiveUser({ id: payload.user_id, username: payload.username });
      window.location.href = "home.html";
    } catch (error) {
      renderFormError(form, error.message);
    }
  });
};

const initSignup = () => {
  const form = document.querySelector("[data-signup-form]");
  if (!form) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = form.querySelector("input[name='username']").value.trim();
    const password = form.querySelector("input[name='password']").value;
    if (!username || !password) {
      renderFormError(form, "Enter a username and password.");
      return;
    }
    try {
      const payload = await apiRequest("/users", {
        method: "POST",
        body: { username, password },
      });
      setActiveUser({ id: payload.id, username: payload.username });
      window.location.href = "home.html";
    } catch (error) {
      renderFormError(form, error.message);
    }
  });
};

const renderQuizList = (list, quizzes) => {
  list.innerHTML = "";
  if (!quizzes.length) {
    const empty = document.createElement("p");
    empty.textContent = "No quizzes yet.";
    list.appendChild(empty);
    return;
  }
  quizzes.forEach((quiz) => {
    const item = document.createElement("div");
    item.className = "panel";
    const scoreText =
      quiz.status === "completed" && quiz.correct_count !== null
        ? `${quiz.correct_count}/${quiz.total_questions} (${Math.round(
            quiz.score_percent || 0
          )}%)`
        : "In progress";
    item.innerHTML = `
      <strong>${quiz.prompt}</strong>
      <p>Score: ${scoreText}</p>
    `;
    list.appendChild(item);
  });
};

const loadQuizList = (list, userId) => {
  list.innerHTML = "<p>Loading quizzes...</p>";
  apiRequest(`/quizzes?user_id=${encodeURIComponent(userId)}`)
    .then((quizzes) => renderQuizList(list, quizzes))
    .catch((error) => {
      list.innerHTML = "";
      const message = document.createElement("p");
      message.textContent = `Unable to load quizzes: ${error.message}`;
      list.appendChild(message);
    });
};

const initHome = () => {
  const state = requireUser();
  const list = document.querySelector("[data-quiz-list]");
  const username = document.querySelector("[data-username]");
  if (username) {
    username.textContent = state.user.username;
  }
  if (list) {
    loadQuizList(list, state.user.id);
  }
  const refresh = document.querySelector("[data-refresh-quizzes]");
  if (refresh && list) {
    refresh.addEventListener("click", () => {
      loadQuizList(list, state.user.id);
    });
  }
  const createBtn = document.querySelector("[data-create-quiz]");
  if (createBtn) {
    createBtn.addEventListener("click", async () => {
      const topic = document.querySelector("textarea[name='topic']").value.trim();
      const prompt = topic || "Surprise Topic";
      createBtn.disabled = true;
      try {
        const payload = await apiRequest("/quizzes/generate", {
          method: "POST",
          body: { user_id: state.user.id, prompt },
        });
        updateState({
          currentQuizId: payload.id,
          currentQuizPublic: payload.quiz_public,
          currentQuizPrompt: payload.prompt,
          currentIndex: 0,
          currentAnswers: [],
        });
        window.location.href = "quiz.html";
      } catch (error) {
        alert(`Unable to create quiz: ${error.message}`);
      } finally {
        createBtn.disabled = false;
      }
    });
  }
  const logout = document.querySelector("[data-logout]");
  if (logout) {
    logout.addEventListener("click", () => {
      clearSession();
      window.location.href = "index.html";
    });
  }
};

const formatFeedback = (feedback) => {
  const verdict = feedback.is_correct ? "Correct! :)" : "Incorrect :(";
  const explanation = feedback.explanation ? ` ${feedback.explanation}` : "";
  return `${verdict}${explanation}`;
};

const renderQuestion = (state, elements) => {
  const { counter, prompt, options, feedback, submit, next } = elements;
  const quizPublic = state.currentQuizPublic;
  const question = quizPublic?.questions?.[state.currentIndex];
  if (!question || !options || !prompt || !counter) {
    return;
  }
  counter.textContent = `${state.currentIndex + 1}/${quizPublic.questions.length}`;
  prompt.textContent = question.prompt;
  options.innerHTML = "";
  question.options.forEach((option) => {
    const wrapper = document.createElement("label");
    wrapper.className = "quiz-option";
    wrapper.innerHTML = `
      <input type="radio" name="choice" value="${option.key}">
      <span>${option.key}. ${option.text}</span>
    `;
    options.appendChild(wrapper);
  });
  const existing = state.currentAnswers?.[state.currentIndex];
  if (feedback) {
    feedback.classList.toggle("incorrect", existing ? !existing.is_correct : false);
    feedback.textContent = existing
      ? formatFeedback(existing)
      : "Choose an answer to see the explanation.";
  }
  if (submit) {
    submit.disabled = Boolean(existing);
  }
  if (next) {
    next.disabled = !existing;
  }
};

const initQuiz = () => {
  const state = requireUser();
  if (!state.currentQuizId || !state.currentQuizPublic) {
    window.location.href = "home.html";
    return;
  }
  const elements = {
    counter: document.querySelector("[data-counter]"),
    prompt: document.querySelector("[data-question]"),
    options: document.querySelector("[data-options]"),
    feedback: document.querySelector("[data-feedback]"),
    submit: document.querySelector("[data-submit-answer]"),
    next: document.querySelector("[data-next-question]"),
  };

  renderQuestion(state, elements);

  if (!elements.submit || !elements.next) {
    return;
  }

  elements.submit.addEventListener("click", async () => {
    const selected = document.querySelector("input[name='choice']:checked");
    if (!selected) {
      return;
    }
    const quizPublic = state.currentQuizPublic;
    const question = quizPublic.questions[state.currentIndex];
    try {
      const payload = await apiRequest(`/quizzes/${state.currentQuizId}/answers`, {
        method: "POST",
        body: {
          question_index: question.index,
          selected_option_key: selected.value,
        },
      });
      state.currentAnswers[state.currentIndex] = payload.feedback;
      saveState(state);
      renderQuestion(state, elements);
    } catch (error) {
      alert(`Unable to submit answer: ${error.message}`);
    }
  });

  elements.next.addEventListener("click", () => {
    if (!state.currentAnswers?.[state.currentIndex]) {
      return;
    }
    state.currentIndex += 1;
    if (state.currentIndex >= state.currentQuizPublic.questions.length) {
      saveState(state);
      window.location.href = "results.html";
      return;
    }
    saveState(state);
    renderQuestion(state, elements);
  });

  const logout = document.querySelector("[data-logout]");
  if (logout) {
    logout.addEventListener("click", () => {
      clearSession();
      window.location.href = "index.html";
    });
  }
};

const optionTextForKey = (options, key) => {
  if (!options || !key) {
    return "No answer";
  }
  const match = options.find((option) => option.key === key);
  return match ? `${match.key}. ${match.text}` : "Unknown option";
};

const initResults = () => {
  const state = requireUser();
  const summary = document.querySelector("[data-score]");
  const list = document.querySelector("[data-results-list]");
  if (!state.currentQuizId) {
    window.location.href = "home.html";
    return;
  }
  if (summary) {
    summary.textContent = "Loading results...";
  }
  if (list) {
    list.innerHTML = "";
  }
  apiRequest(`/quizzes/${state.currentQuizId}/results`)
    .then((results) => {
      if (summary) {
        summary.textContent = `${results.score.correct_count}/${
          results.score.total_questions
        } correct (${Math.round(results.score.score_percent)}%)`;
      }
      if (list) {
        list.innerHTML = "";
        results.questions.forEach((question, index) => {
          const item = document.createElement("div");
          item.className = `panel result-item ${
            question.is_correct ? "result-correct" : "result-incorrect"
          }`;
          const selectedText = optionTextForKey(
            question.options,
            question.selected_option_key
          );
          const correctText = optionTextForKey(
            question.options,
            question.correct_option_key
          );
          const verdictText = question.is_correct ? "Correct" : "Incorrect";
          const explanation = question.explanation ? ` ${question.explanation}` : "";
          item.innerHTML = `
            <strong>Q${index + 1}: ${question.prompt}</strong>
            <p>Your answer: ${selectedText}</p>
            <p>Correct answer: ${correctText}</p>
            <p class="result-verdict ${
              question.is_correct ? "is-correct" : "is-incorrect"
            }">${verdictText}.${explanation}</p>
          `;
          list.appendChild(item);
        });
      }
    })
    .catch((error) => {
      if (summary) {
        summary.textContent = `Unable to load results: ${error.message}`;
      }
    });

  const back = document.querySelector("[data-back]");
  if (back) {
    back.addEventListener("click", () => {
      window.location.href = "home.html";
    });
  }
  const logout = document.querySelector("[data-logout]");
  if (logout) {
    logout.addEventListener("click", () => {
      clearSession();
      window.location.href = "index.html";
    });
  }
};

const init = () => {
  const page = document.body?.dataset?.page;
  if (!page) {
    return;
  }
  if (page === "login") {
    initLogin();
  }
  if (page === "signup") {
    initSignup();
  }
  if (page === "home") {
    initHome();
  }
  if (page === "quiz") {
    initQuiz();
  }
  if (page === "results") {
    initResults();
  }
};

document.addEventListener("DOMContentLoaded", init);
