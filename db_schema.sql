CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    first_name VARCHAR NOT NULL,
    last_name VARCHAR NOT NULL,
    password VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    super_user BOOLEAN DEFAULT FALSE,
    bb_balance INTEGER DEFAULT 100
);

CREATE INDEX IF NOT EXISTS ix_users_first_name ON users(first_name);
CREATE INDEX IF NOT EXISTS ix_users_last_name ON users(last_name);

CREATE TABLE IF NOT EXISTS refresh_token (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS club (
    id SERIAL PRIMARY KEY,
    name VARCHAR,
    league_name VARCHAR,
    nationality_name VARCHAR,
    overall INTEGER,
    attack INTEGER,
    midfield INTEGER,
    defence INTEGER,
    home_stadium VARCHAR,
    logo_url VARCHAR
);

CREATE INDEX IF NOT EXISTS ix_club_name ON club(name);
CREATE INDEX IF NOT EXISTS ix_club_league_name ON club(league_name);
CREATE INDEX IF NOT EXISTS ix_club_nationality_name ON club(nationality_name);
CREATE INDEX IF NOT EXISTS ix_club_overall ON club(overall);
CREATE INDEX IF NOT EXISTS ix_club_attack ON club(attack);
CREATE INDEX IF NOT EXISTS ix_club_midfield ON club(midfield);
CREATE INDEX IF NOT EXISTS ix_club_defence ON club(defence);
CREATE INDEX IF NOT EXISTS ix_club_home_stadium ON club(home_stadium);
CREATE INDEX IF NOT EXISTS ix_club_logo_url ON club(logo_url);

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    short_name VARCHAR,
    long_name VARCHAR,
    overall INTEGER,
    dob TIMESTAMP,
    height_cm INTEGER,
    weight_kg INTEGER,
    club_team_id INTEGER REFERENCES club(id) ON DELETE CASCADE,
    nationality_name VARCHAR,
    preferred_foot VARCHAR,
    weak_foot INTEGER,
    skill_moves INTEGER,
    work_rate VARCHAR,
    player_face_url VARCHAR
);

CREATE INDEX IF NOT EXISTS ix_players_short_name ON players(short_name);
CREATE INDEX IF NOT EXISTS ix_players_long_name ON players(long_name);
CREATE INDEX IF NOT EXISTS ix_players_overall ON players(overall);
CREATE INDEX IF NOT EXISTS ix_players_dob ON players(dob);
CREATE INDEX IF NOT EXISTS ix_players_height_cm ON players(height_cm);
CREATE INDEX IF NOT EXISTS ix_players_weight_kg ON players(weight_kg);
CREATE INDEX IF NOT EXISTS ix_players_nationality_name ON players(nationality_name);
CREATE INDEX IF NOT EXISTS ix_players_preferred_foot ON players(preferred_foot);
CREATE INDEX IF NOT EXISTS ix_players_weak_foot ON players(weak_foot);
CREATE INDEX IF NOT EXISTS ix_players_skill_moves ON players(skill_moves);
CREATE INDEX IF NOT EXISTS ix_players_work_rate ON players(work_rate);
CREATE INDEX IF NOT EXISTS ix_players_player_face_url ON players(player_face_url);

CREATE TABLE IF NOT EXISTS positions (
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    position VARCHAR(20) NOT NULL,
    PRIMARY KEY (player_id, position)
);

CREATE TABLE IF NOT EXISTS player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL UNIQUE REFERENCES players(id) ON DELETE CASCADE,
    pace INTEGER,
    shooting INTEGER,
    passing INTEGER,
    dribbling INTEGER,
    defending INTEGER,
    physic INTEGER
);

CREATE TABLE IF NOT EXISTS goalkeeper_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL UNIQUE REFERENCES players(id) ON DELETE CASCADE,
    diving INTEGER,
    handling INTEGER,
    kicking INTEGER,
    positioning INTEGER,
    reflexes INTEGER,
    speed INTEGER
);

CREATE TABLE IF NOT EXISTS favourite_clubs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    club_id INTEGER REFERENCES club(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favourite_players (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE
);

-- legacy match results table
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    round VARCHAR,
    date VARCHAR NOT NULL,
    time VARCHAR,
    team1 VARCHAR NOT NULL,
    team2 VARCHAR NOT NULL,
    team1_score INTEGER,
    team2_score INTEGER,
    winner VARCHAR,
    league VARCHAR
);

CREATE TABLE IF NOT EXISTS fixtures (
    id SERIAL PRIMARY KEY,
    date VARCHAR NOT NULL,
    home_team VARCHAR NOT NULL,
    away_team VARCHAR NOT NULL,
    league VARCHAR,
    status VARCHAR,
    away_team_score VARCHAR,
    home_team_score VARCHAR,
    winner VARCHAR
);

CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    fixture_id INTEGER REFERENCES fixtures(id) ON DELETE CASCADE,
    prediction_away_score INTEGER NOT NULL,
    prediction_home_score INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS league_standings (
    id SERIAL PRIMARY KEY,
    position INTEGER NOT NULL,
    team_name VARCHAR NOT NULL,
    points INTEGER NOT NULL,
    played_games INTEGER NOT NULL,
    won INTEGER NOT NULL,
    draw INTEGER NOT NULL,
    lost INTEGER NOT NULL,
    goals_for INTEGER NOT NULL,
    goals_against INTEGER NOT NULL,
    goal_difference INTEGER NOT NULL,
    league VARCHAR NOT NULL,
    logo_url VARCHAR
);

CREATE TABLE IF NOT EXISTS form (
    id SERIAL PRIMARY KEY,
    league_standing_id INTEGER NOT NULL REFERENCES league_standings(id) ON DELETE CASCADE,
    outcome VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS custom_players (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    position VARCHAR(10) NOT NULL,
    nationality VARCHAR(100) NOT NULL,
    shirt_number INTEGER NOT NULL,
    preferred_foot VARCHAR(5) NOT NULL,
    pace INTEGER NOT NULL,
    shooting INTEGER NOT NULL,
    passing INTEGER NOT NULL,
    dribbling INTEGER NOT NULL,
    defending INTEGER NOT NULL,
    physic INTEGER NOT NULL,
    overall INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dream_team (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    formation VARCHAR(20) NOT NULL,
    total_score INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dream_team_slot (
    id SERIAL PRIMARY KEY,
    dream_team_id INTEGER NOT NULL REFERENCES dream_team(id) ON DELETE CASCADE,
    position VARCHAR(10) NOT NULL,
    col INTEGER,
    row INTEGER,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS match_comments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id INTEGER NOT NULL REFERENCES fixtures(id) ON DELETE CASCADE,
    content VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS unlocked_players (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE
);
