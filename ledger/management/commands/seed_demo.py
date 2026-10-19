from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from ledger.models import Project, Subproject

class Command(BaseCommand):
    help = 'Create separate, fictional local sample projects. Existing data is never changed.'
    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not settings.DEBUG: raise CommandError('Demo data is available only in DEBUG mode.')
        if User.objects.filter(username='demo').exists():
            self.stdout.write('Demo already exists; no changes made.')
            return
        owner = User.objects.create_user('demo', password='ProjectLedger-Simple-2026!')
        today = timezone.localdate()
        samples = [
            ('Lekki Residence', 'Chidi Okeke', 'Lekki, Lagos', [('Foundation', '1200000', '1200000', 7), ('Block work', '1800000', '1200000', 18), ('Roofing', '2500000', '1000000', 30), ('Plumbing', '850000', '300000', 42), ('Electrical work', '950000', '250000', 50), ('Painting', '600000', '0', 65)]),
            ('Apartment Renovation', 'Ada Williams', 'Ikeja, Lagos', [('Kitchen', '1500000', '900000', 14), ('Tiling', '700000', '500000', 21), ('Painting', '450000', '100000', 28)]),
            ('The Garden Event', 'Nneka Eze', 'Ikoyi, Lagos', [('Venue & setup', '1100000', '300000', 35), ('Catering', '900000', '0', 40)]),
        ]
        for name, client, location, subs in samples:
            project = Project.objects.create(owner=owner, name=name, client=client, location=location)
            for sub, cost, paid, days in subs:
                Subproject.objects.create(project=project, name=sub, cost=Decimal(cost), paid=Decimal(paid), expected_date=today+timedelta(days=days))
        self.stdout.write('Demo ready. Username: demo | Password: ProjectLedger-Simple-2026!')
