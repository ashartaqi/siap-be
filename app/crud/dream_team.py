from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import DreamTeam, DreamTeamSlot, Player
from app.constants import TEAM_TOTAL_OVERALL_MAX
from app.crud.users import create

def _validate_dream_team_slots(db: Session, slots: list) -> int:
    if len(slots) != 11:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Exactly 11 slots must be provided")

    player_ids = [slot.player_id for slot in slots]
    players_by_id = {p.id: p for p in db.query(Player).filter(Player.id.in_(player_ids)).all()}

    missing = [pid for pid in player_ids if pid not in players_by_id]
    if missing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Players not found: {missing}")

    total_score = sum(players_by_id[slot.player_id].overall for slot in slots)
    if total_score > TEAM_TOTAL_OVERALL_MAX:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Total overall cannot exceed {TEAM_TOTAL_OVERALL_MAX}. You used {total_score}."
        )

    return total_score


def get_dream_team(db: Session, user_id: int):
    return db.query(DreamTeam)\
             .filter(DreamTeam.user_id == user_id)\
             .first()

def delete_dream_team(db: Session, user_id: int):
    team = db.query(DreamTeam).filter(
        DreamTeam.user_id == user_id
    ).first()
    if team:
        db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).delete()
        db.delete(team)
        db.commit()
        return True
    return False


def update_dream_team_slot(db: Session, user_id: int, slot_id: int, player_id: int):
    team = db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream team found")

    slot = db.query(DreamTeamSlot).filter(
        DreamTeamSlot.id == slot_id,
        DreamTeamSlot.dream_team_id == team.id
    ).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found in your dream team")

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player {player_id} not found")

    slot.player_id = player_id
    db.flush()

    # Recalculate total_score from all slots
    all_slots = db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).all()
    total = 0
    for s in all_slots:
        p = db.query(Player).filter(Player.id == s.player_id).first()
        if p:
            total += p.overall
    team.total_score = total // len(all_slots) if all_slots else 0

    db.commit()
    db.refresh(team)
    return team

def create_dream_team(db: Session, user_id: int, formation: str, slots: list):
    total_score = _validate_dream_team_slots(db, slots)

    team = DreamTeam(user_id=user_id, formation=formation, total_score=total_score // 11)
    create(db, team)

    for slot in slots:
        create(db, DreamTeamSlot(
            dream_team_id=team.id,
            position=slot.position,
            row=slot.row,
            col=slot.col,
            player_id=slot.player_id
        ))

    return team


def update_dream_team(db: Session, user_id: int, formation: str, slots: list):
    team = db.query(DreamTeam).filter(DreamTeam.user_id == user_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No dream team found")

    total_score = _validate_dream_team_slots(db, slots)

    team.formation = formation
    team.total_score = total_score // 11

    db.query(DreamTeamSlot).filter(DreamTeamSlot.dream_team_id == team.id).delete()
    db.flush()

    for slot in slots:
        db.add(DreamTeamSlot(
            dream_team_id=team.id,
            position=slot.position,
            row=slot.row,
            col=slot.col,
            player_id=slot.player_id
        ))

    db.commit()
    db.refresh(team)
    return team
