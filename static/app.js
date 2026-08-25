const PAGE_SIZE = 20;

const elements = {
  form: document.querySelector("#search-form"),
  input: document.querySelector("#search-input"),
  searchButton: document.querySelector("#search-button"),
  bookList: document.querySelector("#book-list"),
  tableWrapper: document.querySelector("#table-wrapper"),
  loading: document.querySelector("#loading"),
  empty: document.querySelector("#empty"),
  error: document.querySelector("#error"),
  summary: document.querySelector("#result-summary"),
  previousButton: document.querySelector("#previous-button"),
  nextButton: document.querySelector("#next-button"),
  pageIndicator: document.querySelector("#page-indicator"),
};

const state = {
  query: "",
  page: 1,
  totalPages: 0,
  loading: false,
};

const priceFormatter = new Intl.NumberFormat("ko-KR");
let activeRequestController = null;

function setLoading(isLoading) {
  state.loading = isLoading;
  elements.loading.hidden = !isLoading;
  elements.tableWrapper.setAttribute("aria-busy", String(isLoading));
  updatePagination();
}

function updatePagination() {
  const displayedPage = state.totalPages === 0 ? 0 : state.page;
  elements.pageIndicator.textContent = `${displayedPage} / ${state.totalPages}`;
  elements.previousButton.disabled = state.loading || state.page <= 1;
  elements.nextButton.disabled =
    state.loading || state.totalPages === 0 || state.page >= state.totalPages;
}

function renderBooks(books) {
  elements.bookList.replaceChildren();

  for (const book of books) {
    const row = document.createElement("tr");
    const values = [
      book.title,
      book.author,
      book.publisher,
      book.category,
      book.published_date,
      `${priceFormatter.format(book.price)}원`,
      `${book.stock}권`,
    ];

    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }

    elements.bookList.append(row);
  }
}

async function loadBooks() {
  activeRequestController?.abort();
  const requestController = new AbortController();
  activeRequestController = requestController;

  elements.error.hidden = true;
  elements.empty.hidden = true;
  elements.summary.textContent = "";
  elements.bookList.replaceChildren();
  setLoading(true);

  const parameters = new URLSearchParams({
    query: state.query,
    page: String(state.page),
    size: String(PAGE_SIZE),
  });

  try {
    const response = await fetch(`/api/books?${parameters}`, {
      signal: requestController.signal,
    });
    if (!response.ok) {
      throw new Error(`요청에 실패했습니다. (${response.status})`);
    }

    const data = await response.json();
    state.totalPages = data.total_pages;
    renderBooks(data.items);
    elements.summary.textContent = `총 ${priceFormatter.format(data.total)}건`;
    elements.empty.hidden = data.items.length !== 0;
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return;
    }
    state.totalPages = 0;
    elements.error.textContent =
      error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
    elements.error.hidden = false;
  } finally {
    if (activeRequestController === requestController) {
      activeRequestController = null;
      setLoading(false);
    }
  }
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  state.query = elements.input.value.trim();
  state.page = 1;
  loadBooks();
});

elements.previousButton.addEventListener("click", () => {
  if (state.page > 1) {
    state.page -= 1;
    loadBooks();
  }
});

elements.nextButton.addEventListener("click", () => {
  if (state.page < state.totalPages) {
    state.page += 1;
    loadBooks();
  }
});

loadBooks();
