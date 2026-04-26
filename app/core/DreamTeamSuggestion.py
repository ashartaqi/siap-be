from app.api.constants import TEAM_TOTAL_OVERALL_MAX, VALID_PLAYER_POSITIONS
from app.crud import get_players
from app.core.db import engine
from sqlalchemy.orm import Session
from app.api.deps import get_db
import random

positions = VALID_PLAYER_POSITIONS.copy()

mutation_rate = 0.1

positions["defense"].remove("GK")

db = Session(engine)

goalkeeper_pool = get_players(db, limit=50, position="GK")
defender_pool = get_players(db, limit=150, position=positions["defense"])
midfielder_pool = get_players(db, limit=150, position=positions["midfield"])
attacker_pool = get_players(db, limit=150, position=positions["attacking"])

db.close()

def fitness(team):
    total = 0
    clubs = {}
    nations = {}

    for group in team:
        for p in group:
            total += p.overall
            clubs[p.club_team_id] = clubs.get(p.club_team_id, 0) + 1
            nations[p.nationality_id] = nations.get(p.nationality_id, 0) + 1

    chemistry = 0

    for count in clubs.values():
        if count > 1:
            chemistry += (count - 1) * 3

    for count in nations.values():
        if count > 1:
            chemistry += (count - 1) * 2

    # penalize teams that exceed the max overall
    if total > TEAM_TOTAL_OVERALL_MAX:
        return -9999  # heavily penalize, not hard reject

    return total + chemistry

def create_random_team(goalkeepers, defenders_pool, midfielders_pool, attacker_pool,
                       num_def, num_mid, num_att,
                       max_total_overall, max_attempts=50):

    for _ in range(max_attempts):

        # --- build structured team ---
        gk = [random.choice(goalkeepers)]
        existing_ids = {gk[0].id}

        available_def = [p for p in defenders_pool if p.id not in existing_ids]
        defenders = random.sample(available_def, num_def)
        existing_ids.update(p.id for p in defenders)

        available_mid = [p for p in midfielders_pool if p.id not in existing_ids]
        midfielders = random.sample(available_mid, num_mid)
        existing_ids.update(p.id for p in midfielders)

        available_att = [p for p in attacker_pool if p.id not in existing_ids]
        attackers = random.sample(available_att, num_att)

        team = [gk, defenders, midfielders, attackers]

        # --- compute total overall ---
        total_overall = (
            sum(p.overall for p in gk) +
            sum(p.overall for p in defenders) +
            sum(p.overall for p in midfielders) +
            sum(p.overall for p in attackers)
        )

        # --- constraint check ---
        if total_overall <= max_total_overall:
            return team

    # --- fallback (balanced, not weakest-only) ---
    def balanced_sample(pool, n):
        sorted_pool = sorted(pool, key=lambda p: p.overall, reverse=True)
        top_half = sorted_pool[:max(1, len(sorted_pool)//2)]
        return random.sample(top_half, n)

    gk = [min(goalkeepers, key=lambda p: p.overall)]
    defenders = sorted(defenders_pool, key=lambda p: p.overall)[:num_def]
    midfielders = sorted(midfielders_pool, key=lambda p: p.overall)[:num_mid]
    attackers = sorted(attacker_pool, key=lambda p: p.overall)[:num_att]

    return [gk, defenders, midfielders, attackers]


def initialPopulation(pop_size, goalkeepers, defenders_pool, midfielders_pool, attackers_pool,
                      num_def, num_mid, num_att):
    
    population = []

    for _ in range(pop_size):
        team = create_random_team(
            goalkeepers,
            defenders_pool,
            midfielders_pool,
            attackers_pool,
            num_def,
            num_mid,
            num_att,
            TEAM_TOTAL_OVERALL_MAX
        )
        population.append(team)

    return population

def tournament_selection(population, k=3):
    best = None
    best_fitness = float("-inf")

    # pick k random candidates
    candidates = random.sample(population, k)

    for team in candidates:
        score = fitness(team)

        if score > best_fitness:
            best_fitness = score
            best = team

    return best

def crossover(p1, p2):
    child = []

    # GK
    child.append(p1[0] if random.random() < 0.5 else p2[0])

    # DEF
    combined = list({p.id: p for p in p1[1] + p2[1]}.values())
    child.append(random.sample(combined, len(p1[1])))

    # MID
    combined = list({p.id: p for p in p1[2] + p2[2]}.values())
    child.append(random.sample(combined, len(p1[2])))

    # ATT
    combined = list({p.id: p for p in p1[3] + p2[3]}.values())
    child.append(random.sample(combined, len(p1[3])))

    return child

def mutate(team):
    gk, defenders, midfielders, attackers = team

    existing_ids = {p.id for p in defenders + midfielders + attackers}

    if random.random() < mutation_rate:
        gk = [random.choice(goalkeeper_pool)]

    for i in range(len(defenders)):
        if random.random() < mutation_rate:
            candidates = [p for p in defender_pool if p.id not in existing_ids]
            if candidates:
                existing_ids.discard(defenders[i].id)
                defenders[i] = random.choice(candidates)
                existing_ids.add(defenders[i].id)

    for i in range(len(midfielders)):
        if random.random() < mutation_rate:
            candidates = [p for p in midfielder_pool if p.id not in existing_ids]
            if candidates:
                existing_ids.discard(midfielders[i].id)
                midfielders[i] = random.choice(candidates)
                existing_ids.add(midfielders[i].id)

    for i in range(len(attackers)):
        if random.random() < mutation_rate:
            candidates = [p for p in attacker_pool if p.id not in existing_ids]
            if candidates:
                existing_ids.discard(attackers[i].id)
                attackers[i] = random.choice(candidates)
                existing_ids.add(attackers[i].id)

    return [gk, defenders, midfielders, attackers]

def suggestion(formation: str):
    parts = formation.split("-")

    defenders = int(parts[0])
    midfielders = int(parts[1])
    attackers = int(parts[2])

    population = initialPopulation(
        pop_size=50,
        goalkeepers=goalkeeper_pool,
        defenders_pool=defender_pool,
        midfielders_pool=midfielder_pool,
        attackers_pool=attacker_pool,
        num_def=defenders,
        num_mid=midfielders,
        num_att=attackers
    )

    generations = 50

    for _ in range(generations):

        # elitism (keep best)
        best = max(population, key=fitness)

        new_population = [best]

        while len(new_population) < len(population):

            parent1 = tournament_selection(population, k=3)
            parent2 = tournament_selection(population, k=3)

            child = crossover(parent1, parent2)
            child = mutate(child)

            new_population.append(child)

        population = new_population

    return max(population, key=fitness)
    

#to run- python3 -m app.core.DreamTeamSuggestion

# if __name__ == "__main__":
#     team = suggestion("4-3-3")

#     labels = ["GK", "DEF", "MID", "ATT"]
#     total_overall = 0

#     for label, group in zip(labels, team):
#         for player in group:
#             print(f"{label}: {player.short_name} | Overall: {player.overall}")
#             total_overall += player.overall

#     print(f"\nTotal Overall: {total_overall}")