import random
from dataclasses import dataclass, field
from app.constants import POSITION_GROUPS


@dataclass
class EnginePlayer:
    name: str
    role: str  # "FWD", "MID", "DEF"
    attack: float
    passing: float
    defense: float
    finishing: float
    stamina: float = 100.0


@dataclass
class EngineTeam:
    name: str
    players: list[EnginePlayer]

    def get_players(self, role):
        return [p for p in self.players if p.role == role]

    def avg(self, attr, role=None):
        group = self.players if role is None else self.get_players(role)
        if not group:
            return 0.01  # prevent div by zero
        return sum(getattr(p, attr) for p in group) / len(group)


@dataclass
class MatchStats:
    shots1: int = 0
    shots2: int = 0
    xg1: float = 0.0
    xg2: float = 0.0
    possession1: int = 0
    possession2: int = 0


@dataclass
class MatchState:
    team1: EngineTeam
    team2: EngineTeam
    score1: int = 0
    score2: int = 0
    minute: int = 0
    log: list[str] = field(default_factory=list)
    stats: MatchStats = field(default_factory=MatchStats)


class FootballEngine:
    def __init__(self, team1: EngineTeam, team2: EngineTeam):
        self.state = MatchState(team1, team2)

    def log(self, msg):
        self.state.log.append(f"{self.state.minute:02d}' {msg}")

    def fatigue(self, player, minute):
        return player.stamina * (1 - minute / 200)

    def decide_possession(self):
        t1_mid = self.state.team1.avg("passing", "MID")
        t2_mid = self.state.team2.avg("passing", "MID")
        total = t1_mid + t2_mid
        prob = t1_mid / total if total > 0 else 0.5
        if random.random() < prob:
            self.state.stats.possession1 += 1
            return self.state.team1, self.state.team2
        else:
            self.state.stats.possession2 += 1
            return self.state.team2, self.state.team1

    def build_up(self, attacking, defending):
        atk_mid = attacking.avg("passing", "MID")
        def_mid = defending.avg("passing", "MID")
        total = atk_mid + def_mid
        prob = atk_mid / total if total > 0 else 0.5
        return random.random() < prob

    def create_chance(self, attacking, defending):
        atk = attacking.avg("attack", "FWD")
        dfn = defending.avg("defense", "DEF")
        total = atk + dfn
        prob = atk / total if total > 0 else 0.5
        return random.random() < prob

    def take_shot(self, attacking, defending):
        fwds = attacking.get_players("FWD")
        defs = defending.get_players("DEF")
        striker = random.choice(fwds) if fwds else random.choice(attacking.players)
        defender = random.choice(defs) if defs else random.choice(defending.players)
        total = striker.finishing + defender.defense
        shot_quality = striker.finishing / total if total > 0 else 0.5
        xg = shot_quality * random.uniform(0.1, 0.5)
        if attacking == self.state.team1:
            self.state.stats.shots1 += 1
            self.state.stats.xg1 += xg
        else:
            self.state.stats.shots2 += 1
            self.state.stats.xg2 += xg
        if random.random() < xg:
            return True, striker.name
        return False, striker.name

    def attack_sequence(self, attacking, defending):
        if not self.build_up(attacking, defending):
            return
        self.log(f"{attacking.name} building attack")
        if not self.create_chance(attacking, defending):
            return
        goal, scorer = self.take_shot(attacking, defending)
        if goal:
            if attacking == self.state.team1:
                self.state.score1 += 1
            else:
                self.state.score2 += 1
            self.log(f"GOAL by {scorer}! ({self.state.score1}-{self.state.score2})")
        else:
            self.log(f"{scorer} missed")

    def simulate(self):
        for minute in range(1, 91):
            self.state.minute = minute
            attacking, defending = self.decide_possession()
            if random.random() < 0.7:
                self.attack_sequence(attacking, defending)
        return self.state


# Maps position group names to engine roles
_ENGINE_ROLE = {"GK": "DEF", "DEF": "DEF", "MID": "MID", "ATT": "FWD"}


def map_team_to_engine(team, team_name: str) -> EngineTeam:
    """Convert a DreamTeam ORM object into an EngineTeam for simulation."""
    engine_players = []
    for slot in team.slots:
        p = slot.player
        group = POSITION_GROUPS.get(slot.position, "MID")
        role = _ENGINE_ROLE.get(group, "MID")

        if p.player_stats:
            stats = p.player_stats
            engine_players.append(EnginePlayer(
                name=p.short_name,
                role=role,
                attack=float(stats.shooting or 50),
                passing=float(stats.passing or 50),
                defense=float(stats.defending or 50),
                finishing=float(stats.shooting or 50),
                stamina=float(stats.physic or 100),
            ))
        elif p.goalkeeper_stats:
            gk = p.goalkeeper_stats
            engine_players.append(EnginePlayer(
                name=p.short_name,
                role=role,
                attack=10.0,
                passing=float(gk.kicking or 60),
                defense=float(gk.handling or 80),
                finishing=10.0,
                stamina=100.0,
            ))
        else:
            engine_players.append(EnginePlayer(
                name=p.short_name,
                role=role,
                attack=50.0,
                passing=50.0,
                defense=50.0,
                finishing=50.0,
                stamina=100.0,
            ))

    return EngineTeam(name=team_name, players=engine_players)
