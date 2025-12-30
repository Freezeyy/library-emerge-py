from django.core.management.base import BaseCommand
from django.utils import timezone
from library.models import BorrowRecord

class Command(BaseCommand):
    help = 'Update overdue book statuses'

    def handle(self, *args, **kwargs):
        # Find all borrowed books that are now overdue
        overdue_records = BorrowRecord.objects.filter(
            status__in=['borrowed', 'pending_return'],
            due_date__lt=timezone.now()
        )
        
        count = overdue_records.count()
        overdue_records.update(status='overdue')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {count} overdue book(s)')
        )