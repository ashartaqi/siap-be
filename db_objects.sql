-- 1.
CREATE OR REPLACE VIEW v_players_with_stats AS
SELECT
    p.id,
    p.short_name,
    p.long_name,
    p.overall,
    p.dob,
    p.height_cm,
    p.weight_kg,
    p.club_team_id,
    p.nationality_name,
    p.preferred_foot,
    p.weak_foot,
    p.skill_moves,
    p.work_rate,
    p.player_face_url,
    c.name AS club_name,
    -- outfield stats (NULL for GKs)
    ps.pace,
    ps.shooting,
    ps.passing,
    ps.dribbling,
    ps.defending,
    ps.physic,
    -- goalkeeper stats (NULL for outfield)
    gs.diving,
    gs.handling,
    gs.kicking,
    gs.positioning,
    gs.reflexes,
    gs.speed,
    -- all registered positions collapsed into an array
    ARRAY_AGG(DISTINCT pp.position)
        FILTER (WHERE pp.position IS NOT NULL) AS positions
FROM players          p
LEFT JOIN club           c  ON c.id         = p.club_team_id
LEFT JOIN player_stats   ps ON ps.player_id = p.id
LEFT JOIN goalkeeper_stats gs ON gs.player_id = p.id
LEFT JOIN positions      pp ON pp.player_id = p.id
GROUP BY
    p.id,
    c.name,
    ps.pace, ps.shooting, ps.passing, ps.dribbling, ps.defending, ps.physic,
    gs.diving, gs.handling, gs.kicking, gs.positioning, gs.reflexes, gs.speed;


-- 2.
CREATE OR REPLACE FUNCTION fn_players_for_user(p_user_id INT)
RETURNS TABLE (
    id INT,
    short_name TEXT,
    long_name TEXT,
    overall INT,
    dob TIMESTAMP,
    height_cm INT,
    weight_kg INT,
    club_team_id INT,
    nationality_name TEXT,
    preferred_foot TEXT,
    weak_foot INT,
    skill_moves INT,
    work_rate TEXT,
    player_face_url TEXT,
    club_name TEXT,
    pace INT,
    shooting INT,
    passing INT,
    dribbling INT,
    defending INT,
    physic INT,
    diving INT,
    handling INT,
    kicking INT,
    positioning INT,
    reflexes INT,
    speed INT,
    positions TEXT[],
    is_unlocked BOOLEAN
)
LANGUAGE sql STABLE AS $$
    SELECT
        pvs.*,
        (pvs.overall < 70 OR up.player_id IS NOT NULL) AS is_unlocked
    FROM v_players_with_stats pvs
    LEFT JOIN unlocked_players up
        ON up.player_id = pvs.id
       AND up.user_id   = p_user_id
    ORDER BY pvs.overall DESC;
$$;


-- 3.
CREATE OR REPLACE VIEW v_standings_with_form AS
SELECT
    ls.id,
    ls.position,
    ls.team_name,
    ls.points,
    ls.played_games,
    ls.won,
    ls.draw,
    ls.lost,
    ls.goals_for,
    ls.goals_against,
    ls.goal_difference,
    ls.league,
    ls.logo_url,
    f.id AS form_id,
    f.outcome AS form_outcome
FROM league_standings ls
LEFT JOIN form f ON f.league_standing_id = ls.id
ORDER BY ls.position ASC, f.id DESC;


-- 4.
CREATE OR REPLACE VIEW v_votes_with_users AS
SELECT
    v.id,
    v.user_id,
    u.username,
    u.first_name,
    v.fixture_id,
    v.prediction_home_score,
    v.prediction_away_score
FROM votes v
JOIN users u ON u.id = v.user_id;


-- 5.
CREATE OR REPLACE VIEW v_fav_players AS
SELECT
    fp.user_id,
    pvs.*
FROM favourite_players   fp
JOIN v_players_with_stats pvs ON pvs.id = fp.player_id;


-- 6.
CREATE OR REPLACE VIEW v_fav_teams AS
SELECT
    fc.user_id,
    c.*
FROM favourite_clubs fc
JOIN club c ON c.id = fc.club_id;


-- 7.
CREATE OR REPLACE VIEW v_chat_messages_with_users AS
SELECT
    cm.id,
    cm.user_id,
    u.username,
    u.first_name,
    cm.content,
    cm.created_at
FROM chat_messages cm
JOIN users u ON u.id = cm.user_id
ORDER BY cm.created_at ASC;


-- 8.
CREATE OR REPLACE VIEW v_match_comments_with_users AS
SELECT
    mc.id,
    mc.user_id,
    mc.match_id,
    u.username,
    u.first_name,
    mc.content,
    mc.created_at
FROM match_comments mc
JOIN users u ON u.id = mc.user_id
ORDER BY mc.created_at DESC;


-- 9.
CREATE OR REPLACE VIEW v_dream_team_full AS
SELECT
    dt.id AS dream_team_id,
    dt.user_id,
    dt.formation,
    dt.total_score,
    dts.id AS slot_id,
    dts.position AS slot_position,
    dts.row AS slot_row,
    dts.col AS slot_col,
    dts.player_id,
    p.short_name AS player_short_name,
    p.long_name AS player_long_name,
    p.overall AS player_overall,
    p.player_face_url,
    p.nationality_name,
    p.preferred_foot
FROM dream_team dt
JOIN dream_team_slot dts ON dts.dream_team_id = dt.id
JOIN players p   ON p.id = dts.player_id;


-- 10.
CREATE OR REPLACE VIEW v_battle_eligible_users AS
SELECT DISTINCT
    u.id,
    u.username,
    u.first_name,
    u.last_name,
    u.bb_balance,
    (dt.user_id IS NOT NULL) AS has_dream_team,
    (cp.user_id IS NOT NULL) AS has_custom_player
FROM users u
LEFT JOIN dream_team dt ON dt.user_id = u.id
LEFT JOIN custom_players cp ON cp.user_id = u.id
WHERE dt.user_id IS NOT NULL
   OR cp.user_id IS NOT NULL;


-- Stored Procedures

-- 1.
CREATE OR REPLACE FUNCTION get_unlock_price(p_overall INT)
RETURNS INT
LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF p_overall < 70 THEN RETURN 0;   END IF;  -- FREE_PLAYER_CAP
    IF p_overall < 80 THEN RETURN 30;  END IF;  -- SHOP_PRICE_70_80
    IF p_overall < 85 THEN RETURN 40;  END IF;  -- SHOP_PRICE_80_85
    IF p_overall < 90 THEN RETURN 50;  END IF;  -- SHOP_PRICE_85_90
    RETURN 100;                                  -- SHOP_PRICE_90_PLUS
END;
$$;


-- 2.
CREATE OR REPLACE PROCEDURE sp_rotate_refresh_token(
    p_old_token_id INT,
    p_user_id INT,
    p_new_token_hash TEXT,
    p_expires_at TIMESTAMPTZ
)
LANGUAGE plpgsql AS $$
BEGIN
    DELETE FROM refresh_token
    WHERE id = p_old_token_id
      AND user_id = p_user_id;

    DELETE FROM refresh_token
    WHERE user_id   = p_user_id
      AND expires_at < NOW() AT TIME ZONE 'UTC';

    INSERT INTO refresh_token (user_id, token_hash, expires_at, created_at)
    VALUES (p_user_id, p_new_token_hash, p_expires_at, NOW() AT TIME ZONE 'UTC');
END;
$$;


-- 3.
CREATE OR REPLACE FUNCTION fn_check_and_award_daily_login(p_user_id INT)
RETURNS INT
LANGUAGE plpgsql AS $$
DECLARE
    v_today  TIMESTAMP := DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC');
    v_reward INT := 5; -- DAILY_LOGIN_REWARD
BEGIN
    IF EXISTS (
        SELECT 1 FROM refresh_token
        WHERE user_id   = p_user_id
          AND created_at >= v_today
    ) THEN
        RETURN 0;
    END IF;

    UPDATE users SET bb_balance = bb_balance + v_reward WHERE id = p_user_id;
    RETURN v_reward;
END;
$$;


-- 4.
CREATE OR REPLACE PROCEDURE sp_unlock_player(
    p_user_id INT,
    p_player_id INT
)
LANGUAGE plpgsql AS $$
DECLARE
    v_overall INT;
    v_price INT;
    v_balance INT;
BEGIN
    IF EXISTS (
        SELECT 1 FROM unlocked_players
        WHERE user_id = p_user_id AND player_id = p_player_id
    ) THEN
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

    UPDATE users
    SET bb_balance = bb_balance - v_price
    WHERE id = p_user_id;

    INSERT INTO unlocked_players (user_id, player_id)
    VALUES (p_user_id, p_player_id);
END;
$$;


-- 5.
CREATE OR REPLACE PROCEDURE sp_create_dream_team(
    p_user_id INT,
    p_formation TEXT,
    p_slots JSONB
)
LANGUAGE plpgsql AS $$
DECLARE
    v_slot JSONB;
    v_total INT := 0;
    v_overall INT;
    v_team_id INT;
BEGIN
    IF jsonb_array_length(p_slots) != 11 THEN
        RAISE EXCEPTION 'Exactly 11 slots must be provided, got %',
            jsonb_array_length(p_slots);
    END IF;

    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        SELECT overall INTO v_overall
        FROM players WHERE id = (v_slot->>'player_id')::INT;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Player not found: %', (v_slot->>'player_id')::INT;
        END IF;

        v_total := v_total + v_overall;
    END LOOP;

    IF v_total > 1000 THEN -- TEAM_TOTAL_OVERALL_MAX
        RAISE EXCEPTION 'Total overall cannot exceed 1000. You used %.', v_total;
    END IF;

    INSERT INTO dream_team (user_id, formation, total_score)
    VALUES (p_user_id, p_formation, v_total / 11)
    RETURNING id INTO v_team_id;

    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        INSERT INTO dream_team_slot (dream_team_id, position, row, col, player_id)
        VALUES (
            v_team_id,
            v_slot->>'position',
            (v_slot->>'row')::INT,
            (v_slot->>'col')::INT,
            (v_slot->>'player_id')::INT
        );
    END LOOP;
END;
$$;


-- 6.
CREATE OR REPLACE PROCEDURE sp_update_dream_team(
    p_user_id INT,
    p_formation TEXT,
    p_slots JSONB
)
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
        RAISE EXCEPTION 'Exactly 11 slots must be provided, got %',
            jsonb_array_length(p_slots);
    END IF;

    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        SELECT overall INTO v_overall
        FROM players WHERE id = (v_slot->>'player_id')::INT;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Player not found: %', (v_slot->>'player_id')::INT;
        END IF;

        v_total := v_total + v_overall;
    END LOOP;

    IF v_total > 1000 THEN -- TEAM_TOTAL_OVERALL_MAX
        RAISE EXCEPTION 'Total overall cannot exceed 1000. You used %.', v_total;
    END IF;

    UPDATE dream_team
    SET formation = p_formation, total_score = v_total / 11
    WHERE id = v_team_id;

    DELETE FROM dream_team_slot WHERE dream_team_id = v_team_id;

    FOR v_slot IN SELECT * FROM jsonb_array_elements(p_slots) LOOP
        INSERT INTO dream_team_slot (dream_team_id, position, row, col, player_id)
        VALUES (
            v_team_id,
            v_slot->>'position',
            (v_slot->>'row')::INT,
            (v_slot->>'col')::INT,
            (v_slot->>'player_id')::INT
        );
    END LOOP;
END;
$$;


-- 7.
CREATE OR REPLACE PROCEDURE sp_update_dream_team_slot(
    p_user_id INT,
    p_slot_id INT,
    p_player_id INT
)
LANGUAGE plpgsql AS $$
DECLARE
    v_team_id  INT;
    v_avg      INT;
BEGIN
    SELECT id INTO v_team_id FROM dream_team WHERE user_id = p_user_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No dream team found for user %', p_user_id;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM dream_team_slot
        WHERE id = p_slot_id AND dream_team_id = v_team_id
    ) THEN
        RAISE EXCEPTION 'Slot % not found in your dream team', p_slot_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM players WHERE id = p_player_id) THEN
        RAISE EXCEPTION 'Player % not found', p_player_id;
    END IF;

    UPDATE dream_team_slot
    SET player_id = p_player_id
    WHERE id = p_slot_id;

    -- Recalculate average overall across all slots
    SELECT COALESCE(SUM(p.overall) / NULLIF(COUNT(*), 0), 0)
    INTO v_avg
    FROM dream_team_slot dts
    JOIN players p ON p.id = dts.player_id
    WHERE dts.dream_team_id = v_team_id;

    UPDATE dream_team SET total_score = v_avg WHERE id = v_team_id;
END;
$$;


-- 8.
CREATE OR REPLACE FUNCTION fn_create_chat_message(
    p_user_id INT,
    p_content TEXT
)
RETURNS TABLE(message_id INT, reward INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_today TIMESTAMP := DATE_TRUNC('day', NOW() AT TIME ZONE 'UTC');
    v_reward INT       := 0;
    v_msg_id INT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM chat_messages
        WHERE user_id   = p_user_id
          AND created_at >= v_today
    ) THEN
        v_reward := 20; -- CHAT_REWARD
        UPDATE users SET bb_balance = bb_balance + v_reward WHERE id = p_user_id;
    END IF;

    INSERT INTO chat_messages (user_id, content, created_at)
    VALUES (p_user_id, p_content, NOW() AT TIME ZONE 'UTC')
    RETURNING id INTO v_msg_id;

    RETURN QUERY SELECT v_msg_id, v_reward;
END;
$$;


-- 9.
CREATE OR REPLACE FUNCTION fn_create_match_comment(
    p_user_id INT,
    p_match_id INT,
    p_content TEXT
)
RETURNS TABLE(comment_id INT, reward INT)
LANGUAGE plpgsql AS $$
DECLARE
    v_reward     INT := 10; -- MATCH_COMMENT_REWARD
    v_comment_id INT;
BEGIN
    UPDATE users SET bb_balance = bb_balance + v_reward WHERE id = p_user_id;

    INSERT INTO match_comments (user_id, match_id, content, created_at)
    VALUES (p_user_id, p_match_id, p_content, NOW() AT TIME ZONE 'UTC')
    RETURNING id INTO v_comment_id;

    RETURN QUERY SELECT v_comment_id, v_reward;
END;
$$;
