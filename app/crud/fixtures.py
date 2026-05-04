from sqlalchemy.orm import Session, contains_eager
from sqlalchemy import desc
from fastapi import HTTPException, status
from app.models import Fixtures, LeagueStandings, Form, Votes, User
from app.crud.users import create

def get_fixtures(
    db: Session,
    limit: int = 11,
    league: str = None,
    status_filter: str = None,
    home_team: str = None,
    away_team: str = None,
    date: str = None
):
    query = db.query(Fixtures)
    
    if league:
        query = query.filter(Fixtures.league == league)
    if status_filter:
        if (status_filter == 'FINISHED'):
            query = query.filter(Fixtures.status == status_filter).order_by(Fixtures.date.desc())
        else:
            query = query.filter(Fixtures.status == status_filter)
    if home_team:
        query = query.filter(Fixtures.home_team.ilike(f"%{home_team}%"))
    if away_team:
        query = query.filter(Fixtures.away_team.ilike(f"%{away_team}%"))
    if date:
        query = query.filter(Fixtures.date == date)
    
    return query.limit(limit).all()


def get_upcoming_fixtures(db: Session, limit: int = 10) -> list:
    return (
        db.query(Fixtures)
        .filter(Fixtures.status.in_(["SCHEDULED", "TIMED"]))
        .order_by(Fixtures.date)
        .limit(limit)
        .all()
    )


def get_standings(
    db: Session,
    limit: int = 20,
    league: str = None,
    team_name: str = None
):
    subq = db.query(LeagueStandings.id)

    if league:
        subq = subq.filter(LeagueStandings.league == league)
    if team_name:
        subq = subq.filter(LeagueStandings.team_name.ilike(f"%{team_name}%"))

    subq = subq.order_by(LeagueStandings.position).limit(limit).subquery()

    return (
        db.query(LeagueStandings)
        .join(subq, LeagueStandings.id == subq.c.id)
        .outerjoin(LeagueStandings.forms)
        .options(contains_eager(LeagueStandings.forms))
        .order_by(LeagueStandings.position, desc(Form.id))
        .all()
    )

def get_votes(
    db: Session,
    limit: int = 11,
    fixture_id: int = None
):
    query = db.query(Votes)
    
    if fixture_id:
        query = query.filter(Votes.fixture_id == fixture_id)
    
    return query.limit(limit).all()


def get_votes_with_users(
    db: Session,
    fixture_id: int,
    limit: int = 50,
):
    """Get all votes for a fixture, joined with user info."""
    rows = (
        db.query(
            Votes.id,
            Votes.user_id,
            User.username,
            User.first_name,
            Votes.fixture_id,
            Votes.prediction_home_score,
            Votes.prediction_away_score,
        )
        .join(User, User.id == Votes.user_id)
        .filter(Votes.fixture_id == fixture_id)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": r.username,
            "first_name": r.first_name,
            "fixture_id": r.fixture_id,
            "prediction_home_score": r.prediction_home_score,
            "prediction_away_score": r.prediction_away_score,
        }
        for r in rows
    ]


def create_vote(
    db: Session,
    user_id: int,
    fixture_id: int,
    prediction_home_score: int,
    prediction_away_score: int,
):
    existing = db.query(Votes).filter(Votes.user_id == user_id, Votes.fixture_id == fixture_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Vote already exists for this fixture")

    vote = Votes(
        user_id=user_id,
        fixture_id=fixture_id,
        prediction_home_score=prediction_home_score,
        prediction_away_score=prediction_away_score,
    )
    return create(db, vote, "Error creating vote")



def get_user_votes(db: Session, user_id: int):
    return db.query(Votes).filter(Votes.user_id == user_id).all()


def update_vote(
    db: Session,
    user_id: int,
    fixture_id: int,
    prediction_home_score: int,
    prediction_away_score: int,
):
    """Update the prediction on the user's vote for a specific fixture."""
    vote = db.query(Votes).filter(Votes.user_id == user_id, Votes.fixture_id == fixture_id).first()
    if not vote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No vote found for this fixture")
    
    vote.fixture_id = fixture_id
    vote.prediction_home_score = prediction_home_score
    vote.prediction_away_score = prediction_away_score
    db.commit()
    db.refresh(vote)
    return vote


def delete_vote(db: Session, user_id: int, vote_id: int = None):
    if vote_id:
        vote = db.query(Votes).filter(
            Votes.id == vote_id,
            Votes.user_id == user_id
        ).first()
    else:
        vote = db.query(Votes).filter(Votes.user_id == user_id).first()
    
    if vote:
        db.delete(vote)
        db.commit()
        return True
    return False
