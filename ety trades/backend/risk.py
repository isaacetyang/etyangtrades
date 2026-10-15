from dataclasses import dataclass, field

@dataclass
class RiskManager:
    daily_loss_limit_pct: float = 10.0
    trade_risk_pct: float = 2.0
    max_recovery_attempts: int = 3
    max_consecutive_losses: int = 3
    starting_balance: float = 0.0
    daily_pnl: float = 0.0
    consecutive_losses: int = 0
    recovery_attempts: int = 0
    stopped_reason: str = ""

    def begin_session(self, balance: float):
        self.starting_balance = float(balance)
        self.daily_pnl = 0.0
        self.consecutive_losses = 0
        self.recovery_attempts = 0
        self.stopped_reason = ""

    def stake_for(self, balance: float, requested: float) -> float:
        if balance <= 0 or requested <= 0:
            return 0.0
        cap = balance * self.trade_risk_pct / 100
        return round(min(requested, cap), 2)

    def can_trade(self, balance: float, recovery: bool = False):
        if self.stopped_reason:
            return False, self.stopped_reason
        if self.starting_balance and self.daily_pnl <= -(self.starting_balance * self.daily_loss_limit_pct / 100):
            self.stopped_reason = "Daily loss limit reached."
            return False, self.stopped_reason
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.stopped_reason = "Maximum consecutive losses reached."
            return False, self.stopped_reason
        if recovery and self.recovery_attempts >= self.max_recovery_attempts:
            self.stopped_reason = "Maximum recovery attempts reached."
            return False, self.stopped_reason
        if balance <= 0:
            return False, "Account balance is zero or unavailable."
        return True, "Risk checks passed."

    def record_result(self, profit: float, was_recovery: bool = False):
        self.daily_pnl += float(profit)
        if profit < 0:
            self.consecutive_losses += 1
            if not was_recovery:
                self.recovery_attempts = 0
        else:
            self.consecutive_losses = 0
            self.recovery_attempts = 0
        if was_recovery:
            self.recovery_attempts += 1
