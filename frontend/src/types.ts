// Shapes of the backend's JSON responses (see backend/app/schemas.py).

export type QuizType = "meaning" | "spelling" | "listening";
/** What the learner picks on the home page; "mixed" picks a quiz type per question. */
export type StudyMode = QuizType | "mixed";
export type CardState = "new" | "learning" | "review" | "relearning";

export interface Book {
  id: number;
  name: string;
  description: string | null;
  word_count: number;
  learned: number;
  active: boolean;
}

export interface Stats {
  streak_days: number;
  learned_words: number;
  mastered_words: number;
  today_reviews: number;
  today_correct: number;
  daily: { date: string; reviews: number }[];
}

export interface Today {
  book_id: number;
  daily_new_limit: number;
  new_today: number;
  new_remaining: number;
  due_count: number;
}

export interface Option {
  word_id: number;
  text: string;
}

export interface Question {
  card_id: number;
  quiz_type: QuizType;
  is_new: boolean;
  prompt: string;
  phonetic: string | null;
  audio_text: string | null;
  answer_length: number | null;
  options: Option[];
}

export interface NextResponse {
  done: boolean;
  question: Question | null;
}

export interface AnswerResult {
  is_correct: boolean;
  rating: number;
  word_id: number;
  word: string;
  translation: string;
  state: CardState;
  next_due_at: string;
}

export interface User {
  id: number;
  email: string;
  timezone: string;
  created_at: string;
}
