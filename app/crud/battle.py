from sqlalchemy.orm import Session
from app.models import DreamTeam, CustomPlayer, User

def get_battle_users_from_db(db: Session, current_user_id: int):
    # Fetch all user_ids who have either a dream team or a custom player
    users_with_teams = {u[0] for u in db.query(DreamTeam.user_id).all()}
    users_with_players = {u[0] for u in db.query(CustomPlayer.user_id).all()}
    
    user_ids = users_with_teams.union(users_with_players)
    if current_user_id in user_ids:
        user_ids.remove(current_user_id)
        
    if not user_ids:
        return [], set(), set()
        
    users = db.query(User).filter(User.id.in_(user_ids)).all()
    return users, users_with_teams, users_with_players
