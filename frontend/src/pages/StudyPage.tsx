import { FormEvent, RefObject, useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../api";
import { canSpeak, speak } from "../speech";
import { untilText } from "../time";
import type { AnswerResult, Question, QuizType, StudyMode } from "../types";

interface Props {
  mode: StudyMode;
  onExit: () => void;
}

const LETTERS = ["A", "B", "C", "D"];

function pickQuizType(mode: StudyMode): QuizType {
  if (mode !== "mixed") return mode;
  const types: QuizType[] = canSpeak ? ["meaning", "spelling", "listening"] : ["meaning", "spelling"];
  return types[Math.floor(Math.random() * types.length)];
}

/** What the rating means for the learner, in one line. */
function ratingNote(result: AnswerResult): string | null {
  if (!result.is_correct) return null;
  if (result.rating === 4) return "答得很快，下次间隔会拉长。";
  if (result.rating === 2) return "有点犹豫，会早点再考你。";
  return null;
}

type Phase =
  | { name: "loading" }
  | { name: "asking"; question: Question; shownAt: number }
  | {
      name: "answered";
      question: Question;
      result: AnswerResult;
      chosen: number | null;
      typed?: string;
    }
  | { name: "done" }
  | { name: "error"; message: string };

export default function StudyPage({ mode, onExit }: Props) {
  const [phase, setPhase] = useState<Phase>({ name: "loading" });
  const [spelling, setSpelling] = useState("");
  const [count, setCount] = useState(0);
  const [remaining, setRemaining] = useState<number | null>(null);
  const busy = useRef(false);
  const nextButton = useRef<HTMLButtonElement>(null);

  const refreshRemaining = useCallback(async () => {
    try {
      const t = await api.today();
      setRemaining(t.due_count + t.new_remaining);
    } catch {
      setRemaining(null); // the count is a nice-to-have; never block studying on it
    }
  }, []);

  const loadNext = useCallback(async () => {
    setPhase({ name: "loading" });
    setSpelling("");
    try {
      const data = await api.next(pickQuizType(mode));
      if (data.done || !data.question) {
        setPhase({ name: "done" });
        return;
      }
      setPhase({ name: "asking", question: data.question, shownAt: Date.now() });
      if (data.question.quiz_type !== "spelling" && data.question.audio_text) {
        speak(data.question.audio_text);
      }
    } catch (e) {
      setPhase({ name: "error", message: e instanceof ApiError ? e.message : "加载失败" });
    }
  }, [mode]);

  useEffect(() => {
    void loadNext();
    void refreshRemaining();
  }, [loadNext, refreshRemaining]);

  const submit = useCallback(
    async (choice: number | null, typed?: string) => {
      if (phase.name !== "asking" || busy.current) return;
      busy.current = true;
      const { question, shownAt } = phase;
      try {
        const result = await api.answer({
          card_id: question.card_id,
          quiz_type: question.quiz_type,
          choice_word_id: choice,
          spelling: typed,
          response_ms: Date.now() - shownAt,
        });
        setPhase({ name: "answered", question, result, chosen: choice, typed });
        setCount((c) => c + 1);
        speak(result.word);
        void refreshRemaining();
      } catch (e) {
        setPhase({ name: "error", message: e instanceof ApiError ? e.message : "提交失败" });
      } finally {
        busy.current = false;
      }
    },
    [phase, refreshRemaining],
  );

  useEffect(() => {
    if (phase.name === "answered") nextButton.current?.focus();
  }, [phase.name]);

  // Keyboard: 1-4 or A-D picks an option, Enter goes to the next word.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement) return;
      if (phase.name === "asking" && phase.question.options.length > 0) {
        const key = event.key.toUpperCase();
        const index = "1234".includes(key) ? Number(key) - 1 : LETTERS.indexOf(key);
        const option = phase.question.options[index];
        if (index >= 0 && option) {
          event.preventDefault();
          void submit(option.word_id);
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase, submit]);

  function onSpell(event: FormEvent) {
    event.preventDefault();
    if (spelling.trim()) void submit(null, spelling);
  }

  return (
    <main className="page study">
      <header className="topbar">
        <button className="link" onClick={onExit}>
          结束练习
        </button>
        <span className="hint">
          已答 {count} 题{remaining !== null && remaining > 0 ? `，还剩 ${remaining} 个` : ""}
        </span>
      </header>

      {phase.name === "loading" && <p className="hint center">加载中…</p>}

      {phase.name === "error" && (
        <section className="center">
          <p className="error" role="alert">
            {phase.message}
          </p>
          <button className="primary" onClick={() => void loadNext()}>
            再试一次
          </button>
        </section>
      )}

      {phase.name === "done" && (
        <section className="done">
          <h1>今天的词都过完了</h1>
          <p>
            本轮答了 {count} 题。刚学的词过几分钟还会回来，到时候再打开就能继续。
          </p>
          <button className="primary" onClick={onExit}>
            回到首页
          </button>
        </section>
      )}

      {(phase.name === "asking" || phase.name === "answered") && (
        <QuestionView
          question={phase.question}
          answered={phase.name === "answered" ? phase : null}
          spelling={spelling}
          onSpellingChange={setSpelling}
          onChoose={(id) => void submit(id)}
          onSpell={onSpell}
          onSkip={() => void submit(null, phase.question.quiz_type === "spelling" ? "" : undefined)}
        />
      )}

      {phase.name === "answered" && (
        <Feedback
          result={phase.result}
          typed={phase.question.quiz_type === "spelling" ? phase.typed : undefined}
          onNext={() => void loadNext()}
          buttonRef={nextButton}
        />
      )}
    </main>
  );
}

interface QuestionViewProps {
  question: Question;
  answered: { result: AnswerResult; chosen: number | null } | null;
  spelling: string;
  onSpellingChange: (value: string) => void;
  onChoose: (wordId: number) => void;
  onSpell: (event: FormEvent) => void;
  onSkip: () => void;
}

function QuestionView({
  question,
  answered,
  spelling,
  onSpellingChange,
  onChoose,
  onSpell,
  onSkip,
}: QuestionViewProps) {
  const correctId = answered?.result.word_id;

  return (
    <section className="question" aria-live="polite">
      {question.is_new && !answered && <p className="tag-new">新词</p>}

      {question.quiz_type === "meaning" && (
        <div className="prompt">
          <p className="word">{question.prompt}</p>
          <p className="phonetic">
            {question.phonetic && <span>/{question.phonetic}/</span>}
            {canSpeak && question.audio_text && (
              <button className="speaker" onClick={() => speak(question.audio_text!)} aria-label="朗读">
                ▶ 读音
              </button>
            )}
          </p>
        </div>
      )}

      {question.quiz_type === "listening" && (
        <div className="prompt">
          <button
            className="speaker big"
            onClick={() => question.audio_text && speak(question.audio_text)}
            aria-label="再听一遍"
          >
            ▶ 再听一遍
          </button>
          {!canSpeak && <p className="hint">这个浏览器不支持朗读，换 Chrome 或 Safari 试试。</p>}
        </div>
      )}

      {question.quiz_type === "spelling" && (
        <div className="prompt">
          <p className="translation">{question.prompt}</p>
          {question.answer_length && (
            <p className="blanks" aria-label={`${question.answer_length} 个字母`}>
              {"_ ".repeat(question.answer_length).trim()}
            </p>
          )}
        </div>
      )}

      {question.options.length > 0 && (
        <ol className="sheet">
          {question.options.map((option, i) => {
            let status = "";
            if (answered) {
              if (option.word_id === correctId) status = "correct";
              else if (option.word_id === answered.chosen) status = "wrong";
            }
            return (
              <li key={option.word_id}>
                <button
                  className={`sheet-row ${status}`}
                  disabled={!!answered}
                  onClick={() => onChoose(option.word_id)}
                >
                  <span className="bubble" aria-hidden="true">
                    {LETTERS[i]}
                  </span>
                  <span className={question.quiz_type === "listening" ? "option-word" : "option-text"}>
                    {option.text}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {question.quiz_type === "spelling" && !answered && (
        <form className="spell" onSubmit={onSpell}>
          <input
            autoFocus
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            aria-label="拼写单词"
            value={spelling}
            onChange={(e) => onSpellingChange(e.target.value)}
          />
          <button className="primary" type="submit" disabled={!spelling.trim()}>
            确定
          </button>
        </form>
      )}

      {!answered && (
        <button className="link skip" onClick={onSkip}>
          不认识
        </button>
      )}
    </section>
  );
}

interface FeedbackProps {
  result: AnswerResult;
  typed?: string;
  onNext: () => void;
  buttonRef: RefObject<HTMLButtonElement | null>;
}

function Feedback({ result, typed, onNext, buttonRef }: FeedbackProps) {
  const note = ratingNote(result);
  const showTyped = !result.is_correct && typed !== undefined && typed.trim() !== "";
  return (
    <section className={result.is_correct ? "feedback right" : "feedback wrong"} role="status">
      <p className="verdict">{result.is_correct ? "答对了" : "记一下这个词"}</p>
      {showTyped && (
        <p className="typed">
          你写的是 <SpellingDiff typed={typed!.trim()} answer={result.word} />
        </p>
      )}
      <p className="feedback-word">
        {result.word}
        {canSpeak && (
          <button className="speaker" onClick={() => speak(result.word)} aria-label="朗读">
            ▶
          </button>
        )}
      </p>
      <p className="translation">{result.translation}</p>
      <p className="hint">
        {note ? `${note}` : ""}
        {untilText(result.next_due_at)}再复习
      </p>
      <button ref={buttonRef} className="primary" onClick={onNext}>
        下一个
      </button>
    </section>
  );
}

/** Show the learner's spelling with the letters that differ from the answer marked. */
function SpellingDiff({ typed, answer }: { typed: string; answer: string }) {
  const a = answer.toLowerCase();
  return (
    <span className="diff">
      {Array.from(typed).map((ch, i) => (
        <span key={i} className={ch.toLowerCase() === a[i] ? undefined : "diff-miss"}>
          {ch}
        </span>
      ))}
    </span>
  );
}
