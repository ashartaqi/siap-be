from app.api.constants import TEAM_TOTAL_OVERALL_MAX, VALID_PLAYER_POSITIONS
from app.crud import get_players
from app.core.db import engine
from sqlalchemy.orm import Session
import random

positions = VALID_PLAYER_POSITIONS.copy()
positions["defense"].remove("GK")

mutation_rate = 0.1

db = Session(engine)
goalkeeper_pool = get_players(db, limit=50, position="GK")
defender_pool   = get_players(db, limit=150, position=positions["defense"])
midfielder_pool = get_players(db, limit=150, position=positions["midfield"])
attacker_pool   = get_players(db, limit=150, position=positions["attacking"])
db.close()

def parse_formation(formation: str) -> dict:
    """
    Parse a formation string into a role-count dict.

    Supported formats:
        "4-3-3"     -> {def: 4, mid: [3], att: 3}
        "4-2-3-1"   -> {def: 4, mid: [2, 3], att: 1}
        "3-5-2"     -> {def: 3, mid: [5], att: 2}

    Returns:
        {
            "num_def": int,
            "mid_groups": [int, ...],   # one entry per midfield band
            "num_att": int,
        }
    """
    parts = list(map(int, formation.split("-")))
    if len(parts) < 3:
        raise ValueError(f"Formation '{formation}' must have at least 3 numbers (DEF-MID-ATT).")
    return {
        "num_def":    parts[0],
        "mid_groups": parts[1:-1],
        "num_att":    parts[-1],
    }


def _team_size(config: dict) -> int:
    return 1 + config["num_def"] + sum(config["mid_groups"]) + config["num_att"]

def _group_roles(config: dict) -> list[str]:
    """Return a label per group (for debug printing)."""
    roles = ["GK", "DEF"]
    for i, n in enumerate(config["mid_groups"]):
        roles.append(f"MID{i+1}" if len(config["mid_groups"]) > 1 else "MID")
    roles.append("ATT")
    return roles

def fitness(team: list) -> float:
    total    = 0
    clubs    = {}
    nations  = {}

    for group in team:
        for p in group:
            total += p.overall
            clubs[p.club_team_id]    = clubs.get(p.club_team_id, 0) + 1
            nations[p.nationality_id] = nations.get(p.nationality_id, 0) + 1

    if total > TEAM_TOTAL_OVERALL_MAX:
        return -9999

    chemistry = sum((c - 1) * 3 for c in clubs.values()   if c > 1) \
              + sum((c - 1) * 2 for c in nations.values()  if c > 1)

    return total + chemistry

def _sample_unique(pool: list, n: int, excluded_ids: set) -> list:
    available = [p for p in pool if p.id not in excluded_ids]
    return random.sample(available, n)


def create_random_team(config: dict, max_attempts: int = 50) -> list:
    num_def    = config["num_def"]
    mid_groups = config["mid_groups"]
    num_att    = config["num_att"]

    for _ in range(max_attempts):
        gk = [random.choice(goalkeeper_pool)]
        used = {gk[0].id}

        defenders = _sample_unique(defender_pool, num_def, used)
        used.update(p.id for p in defenders)

        mids = []
        for n in mid_groups:
            band = _sample_unique(midfielder_pool, n, used)
            used.update(p.id for p in band)
            mids.append(band)

        attackers = _sample_unique(attacker_pool, num_att, used)

        team = [gk, defenders, *mids, attackers]

        if sum(p.overall for g in team for p in g) <= TEAM_TOTAL_OVERALL_MAX:
            return team

    # Fallback: pick lowest-overall players
    gk        = [min(goalkeeper_pool, key=lambda p: p.overall)]
    defenders = sorted(defender_pool,   key=lambda p: p.overall)[:num_def]
    mids      = [sorted(midfielder_pool, key=lambda p: p.overall)[:n] for n in mid_groups]
    attackers = sorted(attacker_pool,   key=lambda p: p.overall)[:num_att]

    return [gk, defenders, *mids, attackers]

def initial_population(pop_size: int, config: dict) -> list:
    return [create_random_team(config) for _ in range(pop_size)]

def tournament_selection(population: list, k: int = 3) -> list:
    candidates = random.sample(population, k)
    return max(candidates, key=fitness)

def crossover(p1: list, p2: list) -> list:
    child = []

    for g1, g2 in zip(p1, p2):
        merged = list({p.id: p for p in g1 + g2}.values())
        n = len(g1)
        if len(merged) < n:
            merged = g1
        child.append(random.sample(merged, n))

    return child

def mutate(team: list, config: dict) -> list:
    pools = [goalkeeper_pool, defender_pool,
             *[midfielder_pool] * len(config["mid_groups"]),
             attacker_pool]

    used = {p.id for group in team for p in group}

    mutated = []
    for group, pool in zip(team, pools):
        new_group = list(group)
        for i, player in enumerate(new_group):
            if random.random() < mutation_rate:
                candidates = [p for p in pool if p.id not in used]
                if candidates:
                    used.discard(player.id)
                    new_group[i] = random.choice(candidates)
                    used.add(new_group[i].id)
        mutated.append(new_group)

    return mutated

#main
def suggestion(formation: str) -> list:
    config = parse_formation(formation)

    population  = initial_population(pop_size=50, config=config)
    generations = 50

    for _ in range(generations):
        best         = max(population, key=fitness)
        new_pop      = [best]                           # elitism

        while len(new_pop) < len(population):
            p1    = tournament_selection(population)
            p2    = tournament_selection(population)
            child = crossover(p1, p2)
            child = mutate(child, config)
            new_pop.append(child)

        population = new_pop

    return max(population, key=fitness)

# to run: python3 -m app.ai_models.dream_team
# if __name__ == "__main__":
#     formation = "4-2-3-1"
#     config    = parse_formation(formation)
#     roles     = _group_roles(config)
#     team      = suggestion(formation)
#
#     total_overall = 0
#     for label, group in zip(roles, team):
#         for player in group:
#             print(f"{label}: {player.short_name} | Overall: {player.overall}")
#             total_overall += player.overall
#
#     print(f"\nTotal Overall: {total_overall}")