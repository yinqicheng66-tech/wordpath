"""FSRS-6 spaced-repetition scheduler.

FSRS models each card's memory with two numbers:

- stability (S): days until the chance of recalling the card drops to 90%
- difficulty (D): 1 (easy) to 10 (hard); controls how fast stability grows

After each answer, S and D are updated from the rating, and the next review
is scheduled for the day when the predicted recall probability falls to the
desired retention (90% by default).

This is a port of the reference implementation py-fsrs 6.3.2
(https://github.com/open-spaced-repetition/py-fsrs, MIT License), written
without `match` statements so it runs on Python 3.9. Tests check it against
outputs recorded from py-fsrs. Fuzzing is off by default so results are
deterministic; pass a random number generator to turn it on.
"""
import enum
import math
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Callable, Optional, Sequence, Tuple

DEFAULT_PARAMETERS: Tuple[float, ...] = (
    0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722,
    0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425,
    0.0912, 0.0658, 0.1542,
)  # fmt: skip

STABILITY_MIN = 0.001
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0

# (start, end, factor): how much random spread to add to intervals of each length
FUZZ_RANGES = ((2.5, 7.0, 0.15), (7.0, 20.0, 0.1), (20.0, math.inf, 0.05))


class Rating(enum.IntEnum):
    AGAIN = 1  # 忘了
    HARD = 2  # 模糊
    GOOD = 3  # 认识
    EASY = 4  # 很熟


class CardState(str, enum.Enum):
    new = "new"  # never reviewed
    learning = "learning"  # first short steps (minutes)
    review = "review"  # long-term, scheduled in days
    relearning = "relearning"  # forgotten, back on short steps


@dataclass(frozen=True)
class MemoryState:
    """Everything the scheduler needs to know about one card."""

    state: CardState = CardState.new
    step: Optional[int] = 0
    stability: Optional[float] = None
    difficulty: Optional[float] = None
    due: Optional[datetime] = None
    last_review: Optional[datetime] = None


class Scheduler:
    def __init__(
        self,
        parameters: Sequence[float] = DEFAULT_PARAMETERS,
        desired_retention: float = 0.9,
        learning_steps: Sequence[timedelta] = (
            timedelta(minutes=1),
            timedelta(minutes=10),
        ),
        relearning_steps: Sequence[timedelta] = (timedelta(minutes=10),),
        maximum_interval: int = 36500,
        fuzz: Optional[Callable[[], float]] = None,
    ) -> None:
        if len(parameters) != 21:
            raise ValueError(f"Expected 21 parameters, got {len(parameters)}")
        if not 0 < desired_retention < 1:
            raise ValueError("desired_retention must be between 0 and 1")
        self.w = tuple(parameters)
        self.desired_retention = desired_retention
        self.learning_steps = tuple(learning_steps)
        self.relearning_steps = tuple(relearning_steps)
        self.maximum_interval = maximum_interval
        self.fuzz = fuzz  # e.g. random.random; None means no fuzzing

        self._decay = -self.w[20]
        self._factor = 0.9 ** (1 / self._decay) - 1

    # ----- public API -----

    def retrievability(self, card: MemoryState, now: datetime) -> float:
        """Predicted probability (0-1) that the card is recalled at `now`."""
        if card.last_review is None or card.stability is None:
            return 0.0
        elapsed_days = max(0, (now - card.last_review).days)
        return (1 + self._factor * elapsed_days / card.stability) ** self._decay

    def review(self, card: MemoryState, rating: Rating, now: datetime) -> MemoryState:
        """Return the card's new memory state after answering with `rating` at `now`."""
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        rating = Rating(rating)

        state = card.state
        step = card.step
        stability = card.stability
        difficulty = card.difficulty
        if state == CardState.new:
            state, step = CardState.learning, 0

        days_since = (now - card.last_review).days if card.last_review else None
        same_day = days_since is not None and days_since < 1

        # 1. Update stability and difficulty.
        if stability is None or difficulty is None:
            stability = self._initial_stability(rating)
            difficulty = self._clamp_difficulty(self._initial_difficulty(rating))
        elif same_day:
            stability = self._short_term_stability(stability, rating)
            difficulty = self._next_difficulty(difficulty, rating)
        else:
            r = self.retrievability(card, now)
            stability = self._next_stability(difficulty, stability, r, rating)
            difficulty = self._next_difficulty(difficulty, rating)

        # 2. Decide the next state and interval.
        if state == CardState.review:
            if rating == Rating.AGAIN and self.relearning_steps:
                state, step = CardState.relearning, 0
                interval = self.relearning_steps[0]
            else:
                interval = timedelta(days=self._next_interval(stability))
        else:  # learning or relearning: walk through the short steps
            steps = (
                self.learning_steps
                if state == CardState.learning
                else self.relearning_steps
            )
            state, step, interval = self._next_step(
                state, step, steps, rating, stability
            )

        if self.fuzz is not None and state == CardState.review:
            interval = self._fuzzed(interval)

        return replace(
            card,
            state=state,
            step=step,
            stability=stability,
            difficulty=difficulty,
            due=now + interval,
            last_review=now,
        )

    # ----- short-term steps -----

    def _next_step(
        self,
        state: CardState,
        step: Optional[int],
        steps: Tuple[timedelta, ...],
        rating: Rating,
        stability: float,
    ) -> Tuple[CardState, Optional[int], timedelta]:
        step = step or 0

        def graduate() -> Tuple[CardState, Optional[int], timedelta]:
            return CardState.review, None, timedelta(days=self._next_interval(stability))

        if not steps or (step >= len(steps) and rating != Rating.AGAIN):
            return graduate()
        if rating == Rating.AGAIN:
            return state, 0, steps[0]
        if rating == Rating.HARD:
            if step == 0 and len(steps) == 1:
                return state, step, steps[0] * 1.5
            if step == 0:
                return state, step, (steps[0] + steps[1]) / 2
            return state, step, steps[step]
        if rating == Rating.GOOD:
            if step + 1 == len(steps):
                return graduate()
            return state, step + 1, steps[step + 1]
        return graduate()  # EASY

    # ----- FSRS formulas -----

    def _clamp_difficulty(self, d: float) -> float:
        return min(max(d, MIN_DIFFICULTY), MAX_DIFFICULTY)

    def _clamp_stability(self, s: float) -> float:
        return max(s, STABILITY_MIN)

    def _initial_stability(self, rating: Rating) -> float:
        return self._clamp_stability(self.w[rating - 1])

    def _initial_difficulty(self, rating: Rating) -> float:
        return self.w[4] - math.exp(self.w[5] * (rating - 1)) + 1

    def _next_interval(self, stability: float) -> int:
        days = (stability / self._factor) * (
            self.desired_retention ** (1 / self._decay) - 1
        )
        return min(max(round(days), 1), self.maximum_interval)

    def _short_term_stability(self, stability: float, rating: Rating) -> float:
        increase = math.exp(self.w[17] * (rating - 3 + self.w[18])) * (
            stability ** -self.w[19]
        )
        if rating != Rating.AGAIN:
            increase = max(increase, 1.0)
        return self._clamp_stability(stability * increase)

    def _next_difficulty(self, difficulty: float, rating: Rating) -> float:
        delta = -(self.w[6] * (rating - 3))
        damped = difficulty + (10.0 - difficulty) * delta / 9.0
        # mean reversion toward the initial difficulty of an "Easy" card
        target = self._initial_difficulty(Rating.EASY)
        return self._clamp_difficulty(self.w[7] * target + (1 - self.w[7]) * damped)

    def _next_stability(
        self, difficulty: float, stability: float, r: float, rating: Rating
    ) -> float:
        if rating == Rating.AGAIN:
            s = self._forget_stability(difficulty, stability, r)
        else:
            s = self._recall_stability(difficulty, stability, r, rating)
        return self._clamp_stability(s)

    def _forget_stability(self, difficulty: float, stability: float, r: float) -> float:
        long_term = (
            self.w[11]
            * difficulty ** -self.w[12]
            * ((stability + 1) ** self.w[13] - 1)
            * math.exp((1 - r) * self.w[14])
        )
        short_term = stability / math.exp(self.w[17] * self.w[18])
        return min(long_term, short_term)

    def _recall_stability(
        self, difficulty: float, stability: float, r: float, rating: Rating
    ) -> float:
        hard_penalty = self.w[15] if rating == Rating.HARD else 1
        easy_bonus = self.w[16] if rating == Rating.EASY else 1
        return stability * (
            1
            + math.exp(self.w[8])
            * (11 - difficulty)
            * stability ** -self.w[9]
            * (math.exp((1 - r) * self.w[10]) - 1)
            * hard_penalty
            * easy_bonus
        )

    def _fuzzed(self, interval: timedelta) -> timedelta:
        days = interval.days
        if days < 2.5 or self.fuzz is None:
            return interval
        delta = 1.0
        for start, end, factor in FUZZ_RANGES:
            delta += factor * max(min(float(days), end) - start, 0.0)
        max_ivl = min(round(days + delta), self.maximum_interval)
        min_ivl = min(max(2, round(days - delta)), max_ivl)
        fuzzed = round(self.fuzz() * (max_ivl - min_ivl + 1) + min_ivl)
        return timedelta(days=min(fuzzed, self.maximum_interval))
