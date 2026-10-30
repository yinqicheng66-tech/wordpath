import type {
  AnswerResult,
  Book,
  NextResponse,
  QuizType,
  Stats,
  Today,
  User,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL ?? "") + "/api";
const TOKEN_KEY = "wordpath.token";

export const LOGOUT_EVENT = "wordpath:logout";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be unavailable (private mode); the session just won't persist.
  }
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// The backend speaks English; show Chinese messages to the learner.
const MESSAGES: Record<string, string> = {
  "Incorrect email or password": "邮箱或密码不正确",
  "Email already registered": "这个邮箱已经注册过了，直接登录就行",
  "Choose a word book first": "先选一本词书",
  "Card not found": "这道题已经失效，换下一题吧",
  "Book not found": "找不到这本词书",
};

function describe(status: number, detail: unknown): string {
  if (typeof detail === "string") return MESSAGES[detail] ?? detail;
  if (Array.isArray(detail)) {
    const fields = detail.map((d) => String(d?.loc?.[d.loc.length - 1] ?? ""));
    if (fields.includes("password")) return "密码需要 8 到 72 个字符";
    if (fields.includes("email")) return "邮箱格式不正确";
    return "输入的内容有误，请检查一下";
  }
  return `请求失败（${status}）`;
}

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "连不上服务器。确认后端已经启动后再试一次。");
  }

  if (!response.ok) {
    let detail: unknown = null;
    try {
      detail = (await response.json()).detail;
    } catch {
      // not JSON
    }
    if (response.status >= 500 && detail === null) {
      // No JSON body: the dev proxy could not reach the backend at all.
      throw new ApiError(response.status, "连不上服务器。确认后端已经启动后再试一次。");
    }
    if (response.status === 401 && token) {
      setToken(null);
      window.dispatchEvent(new Event(LOGOUT_EVENT));
    }
    throw new ApiError(response.status, describe(response.status, detail));
  }
  return (await response.json()) as T;
}

interface TokenResponse {
  access_token: string;
}

export const api = {
  register: (email: string, password: string) =>
    request<TokenResponse>("/auth/register", "POST", { email, password }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", "POST", { email, password }),
  me: () => request<User>("/me"),
  books: () => request<Book[]>("/books"),
  enroll: (bookId: number, dailyNewLimit: number) =>
    request<unknown>(`/books/${bookId}/enroll`, "POST", {
      daily_new_limit: dailyNewLimit,
    }),
  today: () => request<Today>("/study/today"),
  stats: () => request<Stats>("/stats/summary"),
  next: (mode: QuizType) => request<NextResponse>(`/study/next?mode=${mode}`),
  answer: (body: {
    card_id: number;
    quiz_type: QuizType;
    choice_word_id?: number | null;
    spelling?: string;
    response_ms?: number;
  }) => request<AnswerResult>("/study/answer", "POST", body),
};
