import { useCallback, useEffect, useState } from "react";

import { ApiError, api } from "../api";
import { canSpeak } from "../speech";
import type { Book, Stats, StudyMode, Today } from "../types";

interface Props {
  onStart: (mode: StudyMode) => void;
  onLogout: () => void;
}

const MODES: { id: StudyMode; name: string; detail: string }[] = [
  { id: "mixed", name: "混合练习", detail: "三种题型随机出，记得最牢" },
  { id: "meaning", name: "看词选义", detail: "看英文，选中文意思" },
  { id: "spelling", name: "看义拼词", detail: "看中文，拼出单词" },
  { id: "listening", name: "听音选词", detail: "听发音，选出单词" },
];

export default function HomePage({ onStart, onLogout }: Props) {
  const [today, setToday] = useState<Today | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [books, setBooks] = useState<Book[]>([]);
  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<StudyMode>("mixed");
  const [limit, setLimit] = useState(20);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [bookList, statsData] = await Promise.all([api.books(), api.stats()]);
      setBooks(bookList);
      setStats(statsData);
      if (bookList.some((b) => b.active)) {
        setToday(await api.today());
        setPicking(false);
      } else {
        setToday(null);
        setPicking(true);
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (today) setLimit(today.daily_new_limit);
  }, [today]);

  async function choose(bookId: number) {
    try {
      await api.enroll(bookId, limit);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "选择词书失败");
    }
  }

  const active = books.find((b) => b.active);
  const modes = canSpeak ? MODES : MODES.filter((m) => m.id !== "listening");

  return (
    <main className="page home">
      <header className="topbar">
        <span className="brand">WordPath</span>
        <button className="link" onClick={onLogout}>
          退出登录
        </button>
      </header>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {stats && <StatsPanel stats={stats} />}

      {active && today && !picking && (
        <>
          <section className="current-book">
            <div className="current-book-head">
              <p className="book-name">{active.name}</p>
              <button className="link" onClick={() => setPicking(true)}>
                换一本
              </button>
            </div>
            <Progress learned={active.learned} total={active.word_count} />
          </section>

          <section className="today" aria-label="今天的任务">
            <p className="today-line">
              <span className="big">{today.due_count}</span>
              <span>个词等你复习</span>
            </p>
            <p className="today-line">
              <span className="big">{today.new_remaining}</span>
              <span>
                个新词可以学（今天已学 {today.new_today} / {today.daily_new_limit}）
              </span>
            </p>
          </section>

          <fieldset className="modes">
            <legend>练习方式</legend>
            {modes.map((m) => (
              <label key={m.id} className={mode === m.id ? "mode selected" : "mode"}>
                <input
                  type="radio"
                  name="mode"
                  value={m.id}
                  checked={mode === m.id}
                  onChange={() => setMode(m.id)}
                />
                <span className="mode-name">{m.name}</span>
                <span className="hint">{m.detail}</span>
              </label>
            ))}
          </fieldset>

          <button className="primary start" onClick={() => onStart(mode)}>
            开始
          </button>
        </>
      )}

      {picking && (
        <section className="books">
          <div className="books-head">
            <h1>{active ? "换一本词书" : "选一本词书"}</h1>
            {active && (
              <button className="link" onClick={() => setPicking(false)}>
                取消
              </button>
            )}
          </div>
          <p className="hint">
            换书不会丢失进度。已经学过的词照常复习，新词改从这本书里出。
          </p>
          <label className="limit">
            每天学
            <input
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(Math.max(1, Math.min(200, Number(e.target.value) || 1)))}
            />
            个新词
          </label>
          {books.length === 0 && (
            <p className="hint">还没有词书。在 backend 目录运行 python -m app.importer 导入单词。</p>
          )}
          <ul>
            {books.map((book) => (
              <li key={book.id} className={book.active ? "active" : undefined}>
                <div className="book-info">
                  <p className="book-name">
                    {book.name}
                    <span className="book-count">{book.word_count} 词</span>
                  </p>
                  {book.description && <p className="hint">{book.description}</p>}
                  {book.learned > 0 && <Progress learned={book.learned} total={book.word_count} />}
                </div>
                {book.active ? (
                  <button className="secondary" onClick={() => void choose(book.id)}>
                    保存
                  </button>
                ) : (
                  <button className="primary" onClick={() => void choose(book.id)}>
                    学这本
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function Progress({ learned, total }: { learned: number; total: number }) {
  const percent = total ? Math.min(100, (learned / total) * 100) : 0;
  return (
    <div className="progress">
      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={learned}
        aria-label="学习进度"
      >
        <div className="progress-fill" style={{ width: `${percent}%` }} />
      </div>
      <span className="hint">
        已学 {learned} / {total}
      </span>
    </div>
  );
}

function StatsPanel({ stats }: { stats: Stats }) {
  const max = Math.max(1, ...stats.daily.map((d) => d.reviews));
  const accuracy =
    stats.today_reviews > 0 ? Math.round((stats.today_correct / stats.today_reviews) * 100) : null;
  return (
    <section className="stats" aria-label="学习统计">
      <div className="streak">
        <span className="streak-number">{stats.streak_days}</span>
        <span className="streak-label">{stats.streak_days > 0 ? "天连续学习" : "今天开始打卡"}</span>
      </div>
      <dl className="stat-list">
        <div>
          <dt>已学</dt>
          <dd>{stats.learned_words}</dd>
        </div>
        <div>
          <dt>已掌握</dt>
          <dd>{stats.mastered_words}</dd>
        </div>
        <div>
          <dt>今日正确率</dt>
          <dd>{accuracy === null ? "–" : `${accuracy}%`}</dd>
        </div>
      </dl>
      <div className="days" aria-label="最近 14 天每天答题数">
        {stats.daily.map((d, i) => (
          <div
            key={d.date}
            className={i === stats.daily.length - 1 ? "day today-bar" : "day"}
            title={`${d.date.slice(5)}：${d.reviews} 题`}
          >
            <div className="day-bar" style={{ height: `${(d.reviews / max) * 100}%` }} />
          </div>
        ))}
      </div>
      <p className="hint days-caption">最近 14 天，每天答题数</p>
    </section>
  );
}
