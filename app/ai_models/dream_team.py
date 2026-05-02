from app.constants import TEAM_TOTAL_OVERALL_MAX, VALID_PLAYER_POSITIONS, FORMATIONS
from app.crud import get_players
from app.core.db import engine
from sqlalchemy.orm import Session
import random

positions = VALID_PLAYER_POSITIONS.copy()
positions["defense"].remove("GK")

mutation_rate = 0.1

db = Session(engine)
goalkeeper_pool = get_players(db, limit=50,  position="GK")
defender_pool   = get_players(db, limit=150, position=positions["defense"])
midfielder_pool = get_players(db, limit=150, position=positions["midfield"])
attacker_pool   = get_players(db, limit=150, position=positions["attacking"])
db.close()

# deduplicate: a player stays only in the FIRST pool they appear in (priority: GK > DEF > MID > ATT)
_seen_ids = set()

def _dedup(pool: list) -> list:
    result = []
    for p in pool:
        if p.id not in _seen_ids:
            _seen_ids.add(p.id)
            result.append(p)
    return result

goalkeeper_pool = _dedup(goalkeeper_pool)
defender_pool   = _dedup(defender_pool)
midfielder_pool = _dedup(midfielder_pool)
attacker_pool   = _dedup(attacker_pool)


def parse_formation(formation: str) -> dict:
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
    roles = ["GK", "DEF"]
    for i, n in enumerate(config["mid_groups"]):
        roles.append(f"MID{i+1}" if len(config["mid_groups"]) > 1 else "MID")
    roles.append("ATT")
    return roles


def fitness(team: list) -> float:
    total   = 0
    clubs   = {}
    nations = {}

    for group in team:
        for p in group:
            total += p.overall
            clubs[p.club_team_id]       = clubs.get(p.club_team_id, 0) + 1
            nations[p.nationality_name] = nations.get(p.nationality_name, 0) + 1

    if total > TEAM_TOTAL_OVERALL_MAX:
        return -9999

    chemistry = sum((c - 1) * 3 for c in clubs.values()  if c > 1) \
              + sum((c - 1) * 2 for c in nations.values() if c > 1)

    return total + chemistry


def _sample_unique(pool: list, n: int, excluded_ids: set) -> list:
    available = [p for p in pool if p.id not in excluded_ids]
    if len(available) < n:
        raise ValueError(f"Not enough players: need {n}, have {len(available)}")
    return random.sample(available, n)


def _pick_lowest(pool: list, n: int, excluded_ids: set) -> list:
    available = [p for p in pool if p.id not in excluded_ids]
    return sorted(available, key=lambda p: p.overall)[:n]


def create_random_team(config: dict, max_attempts: int = 100) -> list:
    num_def    = config["num_def"]
    mid_groups = config["mid_groups"]
    num_att    = config["num_att"]

    for _ in range(max_attempts):
        try:
            gk   = [random.choice(goalkeeper_pool)]
            used = {gk[0].id}

            defenders = _sample_unique(defender_pool, num_def, used)
            used.update(p.id for p in defenders)

            mids = []
            for n in mid_groups:
                band = _sample_unique(midfielder_pool, n, used)
                used.update(p.id for p in band)
                mids.append(band)

            attackers = _sample_unique(attacker_pool, num_att, used)
            used.update(p.id for p in attackers)

            team  = [gk, defenders, *mids, attackers]
            total = sum(p.overall for g in team for p in g)

            if total <= TEAM_TOTAL_OVERALL_MAX:
                return team

        except ValueError:
            continue

    # Fallback: pick lowest-overall unique players
    gk   = [min(goalkeeper_pool, key=lambda p: p.overall)]
    used = {gk[0].id}

    defenders = _pick_lowest(defender_pool, num_def, used)
    used.update(p.id for p in defenders)

    mids = []
    for n in mid_groups:
        band = _pick_lowest(midfielder_pool, n, used)
        used.update(p.id for p in band)
        mids.append(band)

    attackers = _pick_lowest(attacker_pool, num_att, used)
    return [gk, defenders, *mids, attackers]


def initial_population(pop_size: int, config: dict) -> list:
    return [create_random_team(config) for _ in range(pop_size)]


def tournament_selection(population: list, k: int = 3) -> list:
    candidates = random.sample(population, k)
    return max(candidates, key=fitness)


def crossover(p1: list, p2: list, config: dict) -> list:
    group_sizes = [1, config["num_def"], *config["mid_groups"], config["num_att"]]
    child = []
    for (g1, g2), size in zip(zip(p1, p2), group_sizes):
        merged = list({p.id: p for p in g1 + g2}.values())
        if len(merged) < size:
            merged = g1
        child.append(random.sample(merged, size))
    return child


def mutate(team: list, config: dict) -> list:
    pools = [
        goalkeeper_pool,
        defender_pool,
        *[midfielder_pool] * len(config["mid_groups"]),
        attacker_pool,
    ]

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


def _validate_team(team: list, config: dict) -> bool:
    group_sizes = [1, config["num_def"], *config["mid_groups"], config["num_att"]]
    if len(team) != len(group_sizes):
        return False
    for group, size in zip(team, group_sizes):
        if len(group) != size:
            return False
    # check no duplicate player ids across the whole team
    all_ids = [p.id for g in team for p in g]
    return len(all_ids) == len(set(all_ids))


def build_suggestion_response(formation: str, team: list, config: dict) -> dict:
    formation_data = next((f for f in FORMATIONS if f["id"] == formation), None)
    if not formation_data:
        raise ValueError(f"Invalid formation: {formation}")

    gk_group   = team[0]
    def_group  = team[1]
    mid_groups = team[2:-1]
    att_group  = team[-1]

    # top to bottom: attackers, mids, defenders
    outfield_players = []
    outfield_players.extend(att_group)
    for mg in mid_groups:
        outfield_players.extend(mg)
    outfield_players.extend(def_group)

    rows          = formation_data["rows"]
    all_positions = [
        (row_index, col, pos)
        for row_index, row_positions in enumerate(rows)
        for col, pos in enumerate(row_positions)
    ]

    if len(outfield_players) != len(all_positions):
        raise ValueError(
            f"Player count mismatch: {len(outfield_players)} players "
            f"for {len(all_positions)} outfield slots"
        )

    slots         = []
    slot_id       = 1
    total_overall = 0

    for (row_index, col, position), player in zip(all_positions, outfield_players):
        slots.append({
            "id":        slot_id,
            "position":  position,
            "row":       row_index,
            "col":       col,
            "player_id": player.id,
            "player":    player,
        })
        total_overall += player.overall
        slot_id       += 1

    gk = gk_group[0]
    slots.append({
        "id":        slot_id,
        "position":  "GK",
        "row":       None,
        "col":       None,
        "player_id": gk.id,
        "player":    gk,
    })
    total_overall += gk.overall

    return {
        "id":          1,
        "formation":   formation,
        "slots":       slots,
        "total_score": total_overall // 11,
    }


def suggestion(formation: str) -> dict:
    config     = parse_formation(formation)
    population = initial_population(pop_size=50, config=config)

    for _ in range(50):
        valid_pop = [t for t in population if _validate_team(t, config)]
        if not valid_pop:
            valid_pop = population

        best    = max(valid_pop, key=fitness)
        new_pop = [best]

        while len(new_pop) < len(population):
            p1    = tournament_selection(valid_pop)
            p2    = tournament_selection(valid_pop)
            child = crossover(p1, p2, config)
            child = mutate(child, config)

            if _validate_team(child, config):
                new_pop.append(child)
            else:
                new_pop.append(create_random_team(config))

        population = new_pop

    valid_pop = [t for t in population if _validate_team(t, config)]
    if not valid_pop:
        valid_pop = population

    best_team = max(valid_pop, key=fitness)
    return build_suggestion_response(formation, best_team, config)


# to run: python3 -m app.ai_models.dream_team
if __name__ == "__main__":
    formation = "4-2-3-1"
    config    = parse_formation(formation)
    roles     = _group_roles(config)
    result    = suggestion(formation)

    print(f"Formation: {result['formation']}")
    print(f"Total score: {result['total_score']}\n")
    for slot in result["slots"]:
        print(f"{slot['position']:4}: {slot['player'].short_name} ({slot['player'].overall})")