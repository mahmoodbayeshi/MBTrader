# Package Scheduler.
from apscheduler.schedulers.background import BlockingScheduler
from pytz import utc

# Main cronjob function.
from analyze import start_analyze
from signals import performance_static
from telbot import tg_updater
from utils import check_run_arg,makedirs,is_production_stage
from price_monitoring import start_monitoring
import os,sys
os.environ['TZ'] = 'Europe/London'


if __name__ == '__main__':
    makedirs()
    args = sys.argv[1:]
    # Create an instance of scheduler and add function.
    job_defaults={
        'coalesce': False,
        'max_instances': 1
    }
    scheduler = BlockingScheduler(job_defaults=job_defaults, timezone=utc)
    scheduler.add_job(start_analyze,'cron',minute="*/5",second=5,misfire_grace_time=300)
    scheduler.add_job(performance_static,'cron',hour="23",minute='57',misfire_grace_time=300)
    if not check_run_arg('--no-tel'):
        scheduler.add_job(tg_updater,'date')
    scheduler.add_job(start_monitoring,'date')
    scheduler.start()
