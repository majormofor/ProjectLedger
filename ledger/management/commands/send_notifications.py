from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone
from ledger.models import EmailNotification
from ledger.notifications import deliver, email_ready

class Command(BaseCommand):
    help = 'Send or retry queued project notifications after configuring a sender.'
    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
    def handle(self, *args, **options):
        if not email_ready():
            raise CommandError('Configure EMAIL_HOST and DEFAULT_FROM_EMAIL first. No email was sent.')
        limit = max(1, min(options['limit'], 1000))
        pending = EmailNotification.objects.filter(Q(status='pending') | Q(status='sending', claimed_at__lt=timezone.now()-timedelta(minutes=5)))[:limit]
        sent = sum(deliver(row.pk) for row in pending)
        self.stdout.write(f'{sent} notifications accepted by the mail backend. Remaining pending: {EmailNotification.objects.exclude(status="sent").count()}.')
