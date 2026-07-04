"""
Celery tasks for the predictions app
--------------------------------------
These tasks mirror what the management command does, but run inside Celery
workers - which means they run in a separate process, support retries on
failure, and can be scheduled via Celery Beat.

Setup (when you're ready to add Celery):
    pip install celery redis django-celery-beat

    # betting_analysis/celery.py
    import os
    from celery import Celery
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_analysis.settings')
    app = Celery('betting_analysis')
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.autodiscover_tasks()

    # settings.py additions
    CELERY_BROKER_URL = 'redis://localhost:6379/0'
    CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
    CELERY_BEAT_SCHEDULE = {
        'generate-predictions-midnight': {
            'task': 'predictions.tasks.generate_all_predictions',
            'schedule': crontab(hour=0, minute=0),  # midnight every day
        },
    }

    # Run workers (two terminal windows):
    # celery -A betting_analysis worker --loglevel=info
    # celery -A betting_analysis beat --loglevel=info
"""
from datetime import date, timedelta

# Celery import is guarded so this file doesn't break your project
# if Celery isn't installed yet - the management command works without it.
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    def shared_task(*args, **kwargs):
        """No-op decorator when Celery isn't installed."""
        def decorator(func):
            return func
        return decorator if args and callable(args[0]) else decorator


from predictions.agents.coordinator import get_predictions_for_sport
from predictions.models import Sports


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def generate_predictions_for_sport(self, sport: str, days_ahead: int = 1, force_refresh: bool = False):
    """
    Celery task: generate predictions for one sport.
    Retries up to 3 times with a 5-minute delay on failure.
    Called by generate_all_predictions() below, one task per sport.

    bind=True gives access to `self` (the task instance) so we can
    call self.retry() on transient failures (network errors, rate limits).
    """
    date_from = date.today()
    date_to = date_from + timedelta(days=days_ahead)

    try:
        results = get_predictions_for_sport(
            sport=sport,
            date_from=date_from,
            date_to=date_to,
            force_refresh=force_refresh,
        )
        successes = sum(1 for r in results if "error" not in r)
        errors = sum(1 for r in results if "error" in r)
        return {
            "sport": sport,
            "total": len(results),
            "successes": successes,
            "errors": errors,
        }
    except Exception as exc:
        # Retry on transient errors (network, rate limits)
        # After max_retries, the exception propagates and the task
        # is marked as failed in Celery's result backend.
        raise self.retry(exc=exc)


@shared_task
def generate_all_predictions(days_ahead: int = 1, force_refresh: bool = False):
    """
    Celery task: trigger prediction generation for ALL sports.
    This is the task Celery Beat calls at midnight every day.
    Spawns one sub-task per sport so they run in parallel if you
    have multiple Celery workers.
    """
    for sport in [Sports.FOOTBALL, Sports.BASKETBALL, Sports.TENNIS]:
        generate_predictions_for_sport.delay(
            sport=sport,
            days_ahead=days_ahead,
            force_refresh=force_refresh,
        )
    return f"Queued prediction generation for {len(Sports.values)} sports."