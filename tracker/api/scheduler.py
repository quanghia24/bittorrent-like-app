from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta
from django.utils.timezone import now
from .models import Peer
import logging 

# Set up basic logging configuration
logging.basicConfig(
    filename='tracker.log',  # Log file path
    filemode='a',            # Append to the log file
    format='%(asctime)s %(message)s',  # Log message format
    datefmt='%H:%M:%S',      # Time format in the logs
    level=logging.INFO      # Capture all log levels
)
# Get the logger object
logger = logging.getLogger()

# Add custom filter to the logger

def check_inactive_peers():
    threshold = now() - timedelta(seconds=15)
    inactive_peers = Peer.objects.filter(last_seen__lt=threshold, is_active=True)
    count = inactive_peers.update(is_active=False)
    logger.info(f"Marked {count} peers as inactive.")
    print(f"Marked {count} peers as inactive.")

    inactive_peers = Peer.objects.filter(is_active=False)
    count = inactive_peers.count()
    logger.info(f"currently have {count} peers inactive.")
    print(f"currently have {count} peers inactive.")

    for p in inactive_peers:
        print(f"removed {p.user.username} from existence.")
        p.delete()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_inactive_peers, 'interval', seconds=15)  # Run every 15 seconds
    scheduler.start()
