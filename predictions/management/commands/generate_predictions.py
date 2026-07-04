"""
Management command: generate_predictions
-----------------------------------------
Generates predictions for all upcoming fixtures across all supported sports.
Designed to be run once daily at midnight via cron or Windows Task Scheduler.

Usage:
    python manage.py generate_predictions
    python manage.py generate_predictions --sport football
    python manage.py generate_predictions --sport football --force-refresh
    python manage.py generate_predictions --days-ahead 2

Cron example (Linux/Mac - runs at midnight every day):
    0 0 * * * /path/to/myenv/bin/python /path/to/manage.py generate_predictions

Windows Task Scheduler:
    Program: C:\\path\\to\\myenv\\Scripts\\python.exe
    Arguments: C:\\path\\to\\manage.py generate_predictions
    Trigger: Daily at 12:00 AM
"""
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from predictions.agents.coordinator import get_predictions_for_sport
from predictions.models import Sports


class Command(BaseCommand):
    help = "Generates AI predictions for all upcoming fixtures. Run daily at midnight."

    def add_arguments(self, parser):
        parser.add_argument(
            '--sport',
            type=str,
            choices=['football', 'basketball', 'tennis'],
            default=None,
            help='Generate predictions for one specific sport only. Defaults to all sports.'
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=1,
            help='How many days ahead to fetch fixtures for. Default is 1 (today only).'
        )
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            default=False,
            help='Re-generate predictions even if they already exist for a fixture.'
        )

    def handle(self, *args, **options):
        sport_filter = options['sport']
        days_ahead = options['days_ahead']
        force_refresh = options['force_refresh']

        # Which sports to run for
        if sport_filter:
            sports_to_run = [sport_filter]
        else:
            sports_to_run = [Sports.FOOTBALL, Sports.BASKETBALL, Sports.TENNIS]

        # Date window: today through N days ahead
        date_from = date.today()
        date_to = date_from + timedelta(days=days_ahead)

        self.stdout.write(
            self.style.NOTICE(
                f"\n{'='*50}\n"
                f"Generating predictions\n"
                f"Sports: {', '.join(sports_to_run)}\n"
                f"Date range: {date_from} to {date_to}\n"
                f"Force refresh: {force_refresh}\n"
                f"Started at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'='*50}"
            )
        )

        total_success = 0
        total_errors = 0
        total_cached = 0

        for sport in sports_to_run:
            self.stdout.write(f"\nProcessing {sport.upper()}...")

            try:
                results = get_predictions_for_sport(
                    sport=sport,
                    date_from=date_from,
                    date_to=date_to,
                    force_refresh=force_refresh,
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  Pipeline failed entirely for {sport}: {e}")
                )
                total_errors += 1
                continue

            for result in results:
                fixture_label = f"{result['home_team']} vs {result['away_team']}"

                if "error" in result:
                    self.stdout.write(
                        self.style.ERROR(f"  ✗ {fixture_label}: {result['error']}")
                    )
                    total_errors += 1
                else:
                    prediction = result["prediction"]
                    confidence = prediction["confidence"]

                    # A prediction made before this run started = cache hit
                    from django.utils.dateparse import parse_datetime
                    pred_created = parse_datetime(prediction["created_at"])
                    is_cached = pred_created < timezone.now() - timedelta(minutes=1)

                    if is_cached:
                        self.stdout.write(
                            f"  ↩ {fixture_label}: reused existing prediction ({confidence}% confidence)"
                        )
                        total_cached += 1
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✓ {fixture_label}: predicted ({confidence}% confidence)"
                            )
                        )
                        total_success += 1

        self.stdout.write(
            self.style.NOTICE(
                f"\n{'='*50}\n"
                f"Done.\n"
                f"  New predictions: {total_success}\n"
                f"  Reused (cached): {total_cached}\n"
                f"  Errors:          {total_errors}\n"
                f"Finished at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'='*50}\n"
            )
        )