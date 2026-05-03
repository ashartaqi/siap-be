-- crud.create_user (p_password_hash: bcrypt computed app-side)
CREATE OR REPLACE PROCEDURE sp_create_user(p_username TEXT, p_email TEXT, p_first_name TEXT, p_last_name TEXT, p_password_hash TEXT, p_super_user BOOLEAN DEFAULT FALSE)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO users (username, email, first_name, last_name, password, super_user, bb_balance)
    VALUES (p_username, p_email, p_first_name, p_last_name, p_password_hash, p_super_user, 100);
END;
$$;

-- crud.create_refresh_token (p_token_hash: sha256 computed app-side)
CREATE OR REPLACE PROCEDURE sp_create_refresh_token(p_user_id INT, p_token_hash TEXT, p_expires_at TIMESTAMPTZ)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO refresh_token (user_id, token_hash, expires_at, created_at)
    VALUES (p_user_id, p_token_hash, p_expires_at, NOW());
END;
$$;

-- crud.get_and_validate_refresh_token
CREATE OR REPLACE FUNCTION fn_get_refresh_token(p_token_hash TEXT)
RETURNS SETOF refresh_token
LANGUAGE sql STABLE AS $$
    SELECT * FROM refresh_token WHERE token_hash = p_token_hash AND expires_at > NOW();
$$;

-- crud.add_bb_reward
CREATE OR REPLACE PROCEDURE sp_add_bb_reward(p_user_id INT, p_amount INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE users SET bb_balance = bb_balance + p_amount WHERE id = p_user_id;
END;
$$;

-- crud.check_and_award_daily_login_reward
CREATE OR REPLACE FUNCTION fn_check_and_award_daily_login(p_user_id INT)
RETURNS INT
LANGUAGE plpgsql AS $$
DECLARE
    v_today TIMESTAMP := DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC');
    v_reward INT := 5;
BEGIN
    IF EXISTS (SELECT 1 FROM refresh_token WHERE user_id = p_user_id AND created_at >= v_today) THEN
        RETURN 0;
    END IF;
    UPDATE users SET bb_balance = bb_balance + v_reward WHERE id = p_user_id;
    RETURN v_reward;
END;
$$;

-- crud.rotate_refresh_token (p_new_token_hash: sha256 computed app-side)
CREATE OR REPLACE PROCEDURE sp_rotate_refresh_token(p_old_token_id INT, p_user_id INT, p_new_token_hash TEXT, p_expires_at TIMESTAMPTZ)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM refresh_token WHERE id = p_old_token_id AND user_id = p_user_id;
    DELETE FROM refresh_token WHERE user_id = p_user_id AND expires_at < NOW() AT TIME ZONE 'UTC';
    INSERT INTO refresh_token (user_id, token_hash, expires_at, created_at)
    VALUES (p_user_id, p_new_token_hash, p_expires_at, NOW() AT TIME ZONE 'UTC');
END;
$$;

-- crud.revoke_refresh_token
CREATE OR REPLACE PROCEDURE sp_revoke_refresh_token(p_token_hash TEXT)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM refresh_token WHERE token_hash = p_token_hash;
END;
$$;

-- crud.get_user_by_id
CREATE OR REPLACE FUNCTION fn_get_user_by_id(p_user_id INT)
RETURNS SETOF users
LANGUAGE sql STABLE AS $$
    SELECT * FROM users WHERE id = p_user_id;
$$;

-- crud.authenticate_user (password verification done app-side via bcrypt)
CREATE OR REPLACE FUNCTION fn_get_user_by_email(p_email TEXT)
RETURNS SETOF users
LANGUAGE sql STABLE AS $$
    SELECT * FROM users WHERE email = p_email;
$$;

-- crud.reset_user_password (p_new_hash: bcrypt computed app-side)
CREATE OR REPLACE PROCEDURE sp_reset_user_password(p_email TEXT, p_new_hash TEXT)
LANGUAGE plpgsql AS $$
DECLARE
    v_user_id INT;
BEGIN
    SELECT id INTO v_user_id FROM users WHERE email = p_email;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'User not found';
    END IF;
    DELETE FROM refresh_token WHERE user_id = v_user_id;
    UPDATE users SET password = p_new_hash WHERE id = v_user_id;
END;
$$;

-- crud.get_teams
CREATE OR REPLACE FUNCTION fn_get_teams(
    p_name TEXT DEFAULT NULL,
    p_league_name TEXT DEFAULT NULL,
    p_nationality_name TEXT DEFAULT NULL,
    p_min_overall INT DEFAULT NULL,
    p_max_overall INT DEFAULT NULL,
    p_min_attack INT DEFAULT NULL,
    p_min_midfield INT DEFAULT NULL,
    p_min_defence INT DEFAULT NULL,
    p_team_type TEXT DEFAULT 'club',
    p_skip INT DEFAULT 0,
    p_limit INT DEFAULT 100
)
RETURNS SETOF club
LANGUAGE sql STABLE AS $$
    SELECT * FROM club
    WHERE (p_team_type = 'national' AND league_name = 'Friendly International'
           OR p_team_type != 'national' AND league_name != 'Friendly International')
      AND (p_name IS NULL OR replace(name, ' ', '') ILIKE '%' || replace(p_name, ' ', '') || '%')
      AND (p_league_name IS NULL OR replace(league_name, ' ', '') ILIKE '%' || replace(p_league_name, ' ', '') || '%')
      AND (p_nationality_name IS NULL OR replace(nationality_name, ' ', '') ILIKE '%' || replace(p_nationality_name, ' ', '') || '%')
      AND (p_min_overall IS NULL OR overall >= p_min_overall)
      AND (p_max_overall IS NULL OR overall <= p_max_overall)
      AND (p_min_attack IS NULL OR attack >= p_min_attack)
      AND (p_min_midfield IS NULL OR midfield >= p_min_midfield)
      AND (p_min_defence IS NULL OR defence >= p_min_defence)
    ORDER BY overall DESC
    OFFSET p_skip LIMIT p_limit;
$$;

-- crud.get_club_by_name
CREATE OR REPLACE FUNCTION fn_get_club_by_name(p_name TEXT)
RETURNS SETOF club
LANGUAGE sql STABLE AS $$
    SELECT * FROM club WHERE name = p_name LIMIT 1;
$$;

-- crud.add_fav_team
CREATE OR REPLACE PROCEDURE sp_add_fav_team(p_user_id INT, p_club_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO favourite_clubs (user_id, club_id) VALUES (p_user_id, p_club_id);
END;
$$;

-- crud.get_fav_teams
CREATE OR REPLACE FUNCTION fn_get_fav_teams(p_user_id INT)
RETURNS SETOF club
LANGUAGE sql STABLE AS $$
    SELECT c.* FROM club c
    JOIN favourite_clubs fc ON fc.club_id = c.id
    WHERE fc.user_id = p_user_id
    ORDER BY c.overall DESC;
$$;

-- crud.remove_fav_team
CREATE OR REPLACE PROCEDURE sp_remove_fav_team(p_user_id INT, p_club_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM favourite_clubs WHERE user_id = p_user_id AND club_id = p_club_id;
END;
$$;

-- crud.get_players
CREATE OR REPLACE FUNCTION fn_get_players(
    p_user_id INT DEFAULT NULL,
    p_limit INT DEFAULT 11,
    p_skip INT DEFAULT 0,
    p_team_id INT DEFAULT NULL,
    p_name TEXT DEFAULT NULL,
    p_nationality_name TEXT DEFAULT NULL,
    p_position TEXT DEFAULT NULL,
    p_min_overall INT DEFAULT NULL,
    p_max_overall INT DEFAULT NULL,
    p_min_age INT DEFAULT NULL,
    p_max_age INT DEFAULT NULL,
    p_preferred_foot TEXT DEFAULT NULL,
    p_order_by_stat TEXT DEFAULT NULL,
    p_pace INT DEFAULT NULL,
    p_shooting INT DEFAULT NULL,
    p_passing INT DEFAULT NULL,
    p_dribbling INT DEFAULT NULL,
    p_defending INT DEFAULT NULL,
    p_physic INT DEFAULT NULL,
    p_unlock_status TEXT DEFAULT NULL
)
RETURNS TABLE (
    id INT, short_name TEXT, long_name TEXT, overall INT, dob TIMESTAMP,
    height_cm INT, weight_kg INT, club_team_id INT, nationality_name TEXT,
    preferred_foot TEXT, weak_foot INT, skill_moves INT, work_rate TEXT,
    player_face_url TEXT, club_name TEXT,
    pace INT, shooting INT, passing INT, dribbling INT, defending INT, physic INT,
    diving INT, handling INT, kicking INT, positioning INT, reflexes INT, speed INT,
    positions TEXT[], is_unlocked BOOLEAN
)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN QUERY
    SELECT p.*
    FROM (
        SELECT pvs.*,
               CASE WHEN p_user_id IS NULL THEN TRUE
                    WHEN pvs.overall < 70 THEN TRUE
                    WHEN up.player_id IS NOT NULL THEN TRUE
                    ELSE FALSE END AS is_unlocked
        FROM v_players_with_stats pvs
        LEFT JOIN unlocked_players up
            ON pvs.overall >= 70 AND up.player_id = pvs.id AND up.user_id = p_user_id
    ) p
    WHERE (p_team_id IS NULL OR p.club_team_id = p_team_id)
      AND (p_name IS NULL
           OR replace(p.short_name, ' ', '') ILIKE '%' || replace(p_name, ' ', '') || '%'
           OR replace(p.long_name, ' ', '') ILIKE '%' || replace(p_name, ' ', '') || '%')
      AND (p_nationality_name IS NULL OR replace(p.nationality_name, ' ', '') ILIKE '%' || replace(p_nationality_name, ' ', '') || '%')
      AND (p_position IS NULL OR upper(p_position) = ANY(p.positions))
      AND (p_min_overall IS NULL OR p.overall >= p_min_overall)
      AND (p_max_overall IS NULL OR p.overall <= p_max_overall)
      AND (p_min_age IS NULL OR p.dob::date <= (CURRENT_DATE - (p_min_age || ' years')::INTERVAL)::DATE)
      AND (p_max_age IS NULL OR p.dob::date > (CURRENT_DATE - ((p_max_age + 1) || ' years')::INTERVAL)::DATE)
      AND (p_preferred_foot IS NULL OR p.preferred_foot ILIKE p_preferred_foot)
      AND (p_pace IS NULL OR p.pace = p_pace)
      AND (p_shooting IS NULL OR p.shooting = p_shooting)
      AND (p_passing IS NULL OR p.passing = p_passing)
      AND (p_dribbling IS NULL OR p.dribbling = p_dribbling)
      AND (p_defending IS NULL OR p.defending = p_defending)
      AND (p_physic IS NULL OR p.physic = p_physic)
      AND (p_unlock_status IS NULL OR p_unlock_status = 'all' OR p_user_id IS NULL
           OR (p_unlock_status = 'unlocked' AND p.is_unlocked)
           OR (p_unlock_status = 'locked' AND NOT p.is_unlocked))
    ORDER BY
        CASE WHEN p_order_by_stat = 'pace' THEN p.pace
             WHEN p_order_by_stat = 'shooting' THEN p.shooting
             WHEN p_order_by_stat = 'passing' THEN p.passing
             WHEN p_order_by_stat = 'dribbling' THEN p.dribbling
             WHEN p_order_by_stat = 'defending' THEN p.defending
             WHEN p_order_by_stat = 'physic' THEN p.physic
             WHEN p_order_by_stat = 'diving' THEN p.diving
             WHEN p_order_by_stat = 'handling' THEN p.handling
             WHEN p_order_by_stat = 'kicking' THEN p.kicking
             WHEN p_order_by_stat = 'positioning' THEN p.positioning
             WHEN p_order_by_stat = 'reflexes' THEN p.reflexes
             WHEN p_order_by_stat = 'speed' THEN p.speed
             ELSE p.overall END DESC NULLS LAST,
        p.overall DESC
    LIMIT p_limit OFFSET p_skip;
END;
$$;

-- crud.add_fav_player
CREATE OR REPLACE PROCEDURE sp_add_fav_player(p_user_id INT, p_player_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO favourite_players (user_id, player_id) VALUES (p_user_id, p_player_id);
END;
$$;

-- crud.get_fav_players
CREATE OR REPLACE FUNCTION fn_get_fav_players(p_user_id INT)
RETURNS TABLE (
    id INT, short_name TEXT, long_name TEXT, overall INT, dob TIMESTAMP,
    height_cm INT, weight_kg INT, club_team_id INT, nationality_name TEXT,
    preferred_foot TEXT, weak_foot INT, skill_moves INT, work_rate TEXT,
    player_face_url TEXT, club_name TEXT,
    pace INT, shooting INT, passing INT, dribbling INT, defending INT, physic INT,
    diving INT, handling INT, kicking INT, positioning INT, reflexes INT, speed INT,
    positions TEXT[]
)
LANGUAGE sql STABLE AS $$
    SELECT pvs.* FROM v_players_with_stats pvs
    JOIN favourite_players fp ON fp.player_id = pvs.id
    WHERE fp.user_id = p_user_id
    ORDER BY pvs.overall DESC;
$$;

-- crud.remove_fav_player
CREATE OR REPLACE PROCEDURE sp_remove_fav_player(p_user_id INT, p_player_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM favourite_players WHERE user_id = p_user_id AND player_id = p_player_id;
END;
$$;

-- crud.get_fixtures
CREATE OR REPLACE FUNCTION fn_get_fixtures(
    p_league TEXT DEFAULT NULL,
    p_status TEXT DEFAULT NULL,
    p_home_team TEXT DEFAULT NULL,
    p_away_team TEXT DEFAULT NULL,
    p_date TEXT DEFAULT NULL,
    p_limit INT DEFAULT 11
)
RETURNS SETOF fixtures
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF p_status = 'FINISHED' THEN
        RETURN QUERY
        SELECT * FROM fixtures
        WHERE (p_league IS NULL OR league = p_league)
          AND status = 'FINISHED'
          AND (p_home_team IS NULL OR home_team ILIKE '%' || p_home_team || '%')
          AND (p_away_team IS NULL OR away_team ILIKE '%' || p_away_team || '%')
          AND (p_date IS NULL OR date = p_date)
        ORDER BY date DESC
        LIMIT p_limit;
    ELSE
        RETURN QUERY
        SELECT * FROM fixtures
        WHERE (p_league IS NULL OR league = p_league)
          AND (p_status IS NULL OR status = p_status)
          AND (p_home_team IS NULL OR home_team ILIKE '%' || p_home_team || '%')
          AND (p_away_team IS NULL OR away_team ILIKE '%' || p_away_team || '%')
          AND (p_date IS NULL OR date = p_date)
        LIMIT p_limit;
    END IF;
END;
$$;

-- crud.get_upcoming_fixtures
CREATE OR REPLACE FUNCTION fn_get_upcoming_fixtures(p_limit INT DEFAULT 10)
RETURNS SETOF fixtures
LANGUAGE sql STABLE AS $$
    SELECT * FROM fixtures
    WHERE status IN ('SCHEDULED', 'TIMED')
    ORDER BY date
    LIMIT p_limit;
$$;

-- crud.get_standings
CREATE OR REPLACE FUNCTION fn_get_standings(p_league TEXT DEFAULT NULL, p_team_name TEXT DEFAULT NULL, p_limit INT DEFAULT 20)
RETURNS TABLE (
    id INT, position INT, team_name TEXT, points INT, played_games INT,
    won INT, draw INT, lost INT, goals_for INT, goals_against INT,
    goal_difference INT, league TEXT, logo_url TEXT, forms TEXT[]
)
LANGUAGE sql STABLE AS $$
    SELECT ls.id, ls.position, ls.team_name, ls.points, ls.played_games,
           ls.won, ls.draw, ls.lost, ls.goals_for, ls.goals_against,
           ls.goal_difference, ls.league, ls.logo_url,
           ARRAY_AGG(f.outcome ORDER BY f.id DESC) FILTER (WHERE f.outcome IS NOT NULL)
    FROM league_standings ls
    LEFT JOIN form f ON f.league_standing_id = ls.id
    WHERE (p_league IS NULL OR ls.league = p_league)
      AND (p_team_name IS NULL OR ls.team_name ILIKE '%' || p_team_name || '%')
    GROUP BY ls.id, ls.position, ls.team_name, ls.points, ls.played_games,
             ls.won, ls.draw, ls.lost, ls.goals_for, ls.goals_against,
             ls.goal_difference, ls.league, ls.logo_url
    ORDER BY ls.position
    LIMIT p_limit;
$$;

-- crud.get_votes
CREATE OR REPLACE FUNCTION fn_get_votes(p_fixture_id INT DEFAULT NULL, p_limit INT DEFAULT 11)
RETURNS SETOF votes
LANGUAGE sql STABLE AS $$
    SELECT * FROM votes
    WHERE (p_fixture_id IS NULL OR fixture_id = p_fixture_id)
    LIMIT p_limit;
$$;

-- crud.get_votes_with_users
CREATE OR REPLACE FUNCTION fn_get_votes_with_users(p_fixture_id INT, p_limit INT DEFAULT 50)
RETURNS TABLE (id INT, user_id INT, username TEXT, first_name TEXT, fixture_id INT, prediction_home_score INT, prediction_away_score INT)
LANGUAGE sql STABLE AS $$
    SELECT v.id, v.user_id, u.username, u.first_name, v.fixture_id, v.prediction_home_score, v.prediction_away_score
    FROM votes v
    JOIN users u ON u.id = v.user_id
    WHERE v.fixture_id = p_fixture_id
    LIMIT p_limit;
$$;

-- crud.create_vote
CREATE OR REPLACE PROCEDURE sp_create_vote(p_user_id INT, p_fixture_id INT, p_home_score INT, p_away_score INT)
LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM votes WHERE user_id = p_user_id AND fixture_id = p_fixture_id) THEN
        RAISE EXCEPTION 'Vote already exists for this fixture';
    END IF;
    INSERT INTO votes (user_id, fixture_id, prediction_home_score, prediction_away_score)
    VALUES (p_user_id, p_fixture_id, p_home_score, p_away_score);
END;
$$;

-- crud.get_user_votes
CREATE OR REPLACE FUNCTION fn_get_user_votes(p_user_id INT)
RETURNS SETOF votes
LANGUAGE sql STABLE AS $$
    SELECT * FROM votes WHERE user_id = p_user_id;
$$;

-- crud.update_vote
CREATE OR REPLACE PROCEDURE sp_update_vote(p_user_id INT, p_fixture_id INT, p_home_score INT, p_away_score INT)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE votes
    SET prediction_home_score = p_home_score, prediction_away_score = p_away_score
    WHERE user_id = p_user_id AND fixture_id = p_fixture_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No vote found for this fixture';
    END IF;
END;
$$;

-- crud.delete_vote
CREATE OR REPLACE PROCEDURE sp_delete_vote(p_user_id INT, p_vote_id INT DEFAULT NULL)
LANGUAGE plpgsql AS $$
BEGIN
    IF p_vote_id IS NOT NULL THEN
        DELETE FROM votes WHERE id = p_vote_id AND user_id = p_user_id;
    ELSE
        DELETE FROM votes WHERE user_id = p_user_id;
    END IF;
END;
$$;

-- crud.get_custom_player
CREATE OR REPLACE FUNCTION fn_get_custom_player(p_user_id INT)
RETURNS SETOF custom_players
LANGUAGE sql STABLE AS $$
    SELECT * FROM custom_players WHERE user_id = p_user_id LIMIT 1;
$$;

-- crud.add_custom_player (p_overall, p_position: ML model output passed from app)
CREATE OR REPLACE PROCEDURE sp_add_custom_player(
    p_user_id INT, p_name TEXT, p_nationality TEXT, p_shirt_number INT,
    p_preferred_foot TEXT, p_pace INT, p_shooting INT, p_passing INT,
    p_dribbling INT, p_defending INT, p_physic INT, p_overall INT, p_position TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO custom_players (user_id, name, nationality, shirt_number, preferred_foot, pace, shooting, passing, dribbling, defending, physic, overall, position)
    VALUES (p_user_id, p_name, p_nationality, p_shirt_number, p_preferred_foot, p_pace, p_shooting, p_passing, p_dribbling, p_defending, p_physic, p_overall, p_position);
END;
$$;

-- crud.update_custom_player (p_overall, p_position: ML model output passed from app)
CREATE OR REPLACE PROCEDURE sp_update_custom_player(
    p_user_id INT, p_name TEXT DEFAULT NULL, p_nationality TEXT DEFAULT NULL,
    p_shirt_number INT DEFAULT NULL, p_preferred_foot TEXT DEFAULT NULL,
    p_pace INT DEFAULT NULL, p_shooting INT DEFAULT NULL, p_passing INT DEFAULT NULL,
    p_dribbling INT DEFAULT NULL, p_defending INT DEFAULT NULL, p_physic INT DEFAULT NULL,
    p_overall INT DEFAULT NULL, p_position TEXT DEFAULT NULL
)
LANGUAGE plpgsql AS $$
BEGIN
    UPDATE custom_players
    SET name = COALESCE(p_name, name),
        nationality = COALESCE(p_nationality, nationality),
        shirt_number = COALESCE(p_shirt_number, shirt_number),
        preferred_foot = COALESCE(p_preferred_foot, preferred_foot),
        pace = COALESCE(p_pace, pace),
        shooting = COALESCE(p_shooting, shooting),
        passing = COALESCE(p_passing, passing),
        dribbling = COALESCE(p_dribbling, dribbling),
        defending = COALESCE(p_defending, defending),
        physic = COALESCE(p_physic, physic),
        overall = COALESCE(p_overall, overall),
        position = COALESCE(p_position, position)
    WHERE user_id = p_user_id;
END;
$$;

-- crud.delete_custom_player
CREATE OR REPLACE PROCEDURE sp_delete_custom_player(p_user_id INT)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM custom_players WHERE user_id = p_user_id;
END;
$$;

-- crud.get_dream_team
CREATE OR REPLACE FUNCTION fn_get_dream_team(p_user_id INT)
RETURNS SETOF dream_team
LANGUAGE sql STABLE AS $$
    SELECT * FROM dream_team WHERE user_id = p_user_id LIMIT 1;
$$;

-- crud.delete_dream_team
CREATE OR REPLACE PROCEDURE sp_delete_dream_team(p_user_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_team_id INT;
BEGIN
    SELECT id INTO v_team_id FROM dream_team WHERE user_id = p_user_id;
    IF NOT FOUND THEN RETURN; END IF;
    DELETE FROM dream_team_slot WHERE dream_team_id = v_team_id;
    DELETE FROM dream_team WHERE id = v_team_id;
END;
$$;

-- crud.create_dream_team (validates 11 slots, checks players exist, enforces total cap)
CREATE OR REPLACE PROCEDURE sp_create_dream_team(p_user_id INT, p_formation TEXT, p_slots JSONB)
LANGUAGE plpgsql AS $$
DECLARE
    v_slot JSONB;
    v_total INT := 0;
    v_overall INT;
    v_team_id INT;
BEGIN
    IF jsonb_array_length(p_slots) != 11 THEN
        RAISE EXCEPTION 'Exactly 11 slots must be provided, got %', jsonb_array_length(p_slots);
    END IF;
    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        SELECT overall INTO v_overall FROM players WHERE id = (v_slot->>'player_id')::INT;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Player not found: %', (v_slot->>'player_id')::INT;
        END IF;
        v_total := v_total + v_overall;
    END LOOP;
    IF v_total > 1000 THEN
        RAISE EXCEPTION 'Total overall cannot exceed 1000. You used %.', v_total;
    END IF;
    INSERT INTO dream_team (user_id, formation, total_score)
    VALUES (p_user_id, p_formation, v_total / 11)
    RETURNING id INTO v_team_id;
    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        INSERT INTO dream_team_slot (dream_team_id, position, row, col, player_id)
        VALUES (v_team_id, v_slot->>'position', (v_slot->>'row')::INT, (v_slot->>'col')::INT, (v_slot->>'player_id')::INT);
    END LOOP;
END;
$$;

-- crud.update_dream_team
CREATE OR REPLACE PROCEDURE sp_update_dream_team(p_user_id INT, p_formation TEXT, p_slots JSONB)
LANGUAGE plpgsql AS $$
DECLARE
    v_slot JSONB;
    v_total INT := 0;
    v_overall INT;
    v_team_id INT;
BEGIN
    SELECT id INTO v_team_id FROM dream_team WHERE user_id = p_user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No dream team found for user %', p_user_id;
    END IF;
    IF jsonb_array_length(p_slots) != 11 THEN
        RAISE EXCEPTION 'Exactly 11 slots must be provided, got %', jsonb_array_length(p_slots);
    END IF;
    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        SELECT overall INTO v_overall FROM players WHERE id = (v_slot->>'player_id')::INT;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Player not found: %', (v_slot->>'player_id')::INT;
        END IF;
        v_total := v_total + v_overall;
    END LOOP;
    IF v_total > 1000 THEN
        RAISE EXCEPTION 'Total overall cannot exceed 1000. You used %.', v_total;
    END IF;
    UPDATE dream_team SET formation = p_formation, total_score = v_total / 11 WHERE id = v_team_id;
    DELETE FROM dream_team_slot WHERE dream_team_id = v_team_id;
    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        INSERT INTO dream_team_slot (dream_team_id, position, row, col, player_id)
        VALUES (v_team_id, v_slot->>'position', (v_slot->>'row')::INT, (v_slot->>'col')::INT, (v_slot->>'player_id')::INT);
    END LOOP;
END;
$$;

-- crud.update_dream_team_slot
CREATE OR REPLACE PROCEDURE sp_update_dream_team_slot(p_user_id INT, p_slot_id INT, p_player_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_team_id INT;
    v_avg INT;
BEGIN
    SELECT id INTO v_team_id FROM dream_team WHERE user_id = p_user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No dream team found for user %', p_user_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM dream_team_slot WHERE id = p_slot_id AND dream_team_id = v_team_id) THEN
        RAISE EXCEPTION 'Slot % not found in your dream team', p_slot_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM players WHERE id = p_player_id) THEN
        RAISE EXCEPTION 'Player % not found', p_player_id;
    END IF;
    UPDATE dream_team_slot SET player_id = p_player_id WHERE id = p_slot_id;
    SELECT COALESCE(SUM(p.overall) / NULLIF(COUNT(*), 0), 0)
    INTO v_avg
    FROM dream_team_slot dts
    JOIN players p ON p.id = dts.player_id
    WHERE dts.dream_team_id = v_team_id;
    UPDATE dream_team SET total_score = v_avg WHERE id = v_team_id;
END;
$$;

-- crud.get_chat_messages
CREATE OR REPLACE FUNCTION fn_get_chat_messages(p_limit INT DEFAULT 50)
RETURNS TABLE (id INT, user_id INT, username TEXT, first_name TEXT, content TEXT, created_at TIMESTAMP)
LANGUAGE sql STABLE AS $$
    SELECT cm.id, cm.user_id, u.username, u.first_name, cm.content, cm.created_at
    FROM chat_messages cm
    JOIN users u ON u.id = cm.user_id
    ORDER BY cm.created_at ASC
    LIMIT p_limit;
$$;

-- crud.create_chat_message
CREATE OR REPLACE FUNCTION fn_create_chat_message(p_user_id INT, p_content TEXT)
RETURNS TABLE (message_id INT, reward INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_today TIMESTAMP := DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC');
    v_reward INT := 0;
    v_msg_id INT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chat_messages WHERE user_id = p_user_id AND created_at >= v_today) THEN
        v_reward := 20;
        UPDATE users SET bb_balance = bb_balance + v_reward WHERE id = p_user_id;
    END IF;
    INSERT INTO chat_messages (user_id, content, created_at)
    VALUES (p_user_id, p_content, NOW() AT TIME ZONE 'UTC')
    RETURNING id INTO v_msg_id;
    RETURN QUERY SELECT v_msg_id, v_reward;
END;
$$;

-- crud.get_match_comments
CREATE OR REPLACE FUNCTION fn_get_match_comments(p_match_id INT)
RETURNS TABLE (id INT, user_id INT, match_id INT, username TEXT, first_name TEXT, content TEXT, created_at TIMESTAMP)
LANGUAGE sql STABLE AS $$
    SELECT mc.id, mc.user_id, mc.match_id, u.username, u.first_name, mc.content, mc.created_at
    FROM match_comments mc
    JOIN users u ON u.id = mc.user_id
    WHERE mc.match_id = p_match_id
    ORDER BY mc.created_at DESC;
$$;

-- crud.create_match_comment
CREATE OR REPLACE FUNCTION fn_create_match_comment(p_user_id INT, p_match_id INT, p_content TEXT)
RETURNS TABLE (comment_id INT, reward INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_reward INT := 10;
    v_comment_id INT;
BEGIN
    UPDATE users SET bb_balance = bb_balance + v_reward WHERE id = p_user_id;
    INSERT INTO match_comments (user_id, match_id, content, created_at)
    VALUES (p_user_id, p_match_id, p_content, NOW() AT TIME ZONE 'UTC')
    RETURNING id INTO v_comment_id;
    RETURN QUERY SELECT v_comment_id, v_reward;
END;
$$;

-- crud.get_unlock_price
CREATE OR REPLACE FUNCTION get_unlock_price(p_overall INT)
RETURNS INT
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF p_overall < 70 THEN RETURN 0; END IF;
    IF p_overall < 80 THEN RETURN 30; END IF;
    IF p_overall < 85 THEN RETURN 40; END IF;
    IF p_overall < 90 THEN RETURN 50; END IF;
    RETURN 100;
END;
$$;

-- crud.unlock_player
CREATE OR REPLACE PROCEDURE sp_unlock_player(p_user_id INT, p_player_id INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_overall INT;
    v_price INT;
    v_balance INT;
BEGIN
    IF EXISTS (SELECT 1 FROM unlocked_players WHERE user_id = p_user_id AND player_id = p_player_id) THEN
        RAISE EXCEPTION 'Player already unlocked';
    END IF;
    SELECT overall INTO v_overall FROM players WHERE id = p_player_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Player not found: %', p_player_id;
    END IF;
    v_price := get_unlock_price(v_overall);
    SELECT bb_balance INTO v_balance FROM users WHERE id = p_user_id;
    IF v_balance < v_price THEN
        RAISE EXCEPTION 'Insufficient BB balance. Need % BB.', v_price;
    END IF;
    UPDATE users SET bb_balance = bb_balance - v_price WHERE id = p_user_id;
    INSERT INTO unlocked_players (user_id, player_id) VALUES (p_user_id, p_player_id);
END;
$$;

-- crud.get_battle_users_from_db
CREATE OR REPLACE FUNCTION fn_get_battle_users(p_current_user_id INT)
RETURNS TABLE (id INT, username TEXT, first_name TEXT, last_name TEXT, has_dream_team BOOLEAN, has_custom_player BOOLEAN)
LANGUAGE sql STABLE AS $$
    SELECT DISTINCT u.id, u.username, u.first_name, u.last_name,
           (dt.user_id IS NOT NULL) AS has_dream_team,
           (cp.user_id IS NOT NULL) AS has_custom_player
    FROM users u
    LEFT JOIN dream_team dt ON dt.user_id = u.id
    LEFT JOIN custom_players cp ON cp.user_id = u.id
    WHERE (dt.user_id IS NOT NULL OR cp.user_id IS NOT NULL)
      AND u.id != p_current_user_id;
$$;
