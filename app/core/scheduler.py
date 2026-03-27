from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def register_jobs():
    from app.scripts.jobs import fetch_fixtures, update_fixtures, fetch_leagues

    scheduler.add_job(
        fetch_fixtures,
        trigger="interval",
        hours=12,
        id="fetch_and_update_fixtures",
        replace_existing=True,
    )
    scheduler.add_job(
        update_fixtures,
        trigger="interval",
        hours=6,
        id="update_fixtures",
        replace_existing=True,
    )
    scheduler.add_job(
        fetch_leagues,
        trigger="interval",
        hours=24,
        id="fetch_leagues_job",
        replace_existing=True,
    )

