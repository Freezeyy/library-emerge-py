from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

# Add this new model for user profiles
class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('librarian', 'Librarian'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=15, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student_id} - {self.name}"

    class Meta:
        ordering = ['name']


class Book(models.Model):
    isbn = models.CharField(max_length=13, unique=True)
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=100)
    publisher = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)  # New field
    cover_image = models.ImageField(upload_to='book_covers/', blank=True, null=True)  # New field
    total_copies = models.IntegerField(default=1)
    available_copies = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title']


class BorrowRecord(models.Model):
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('pending_return', 'Pending Return'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    borrow_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    borrow_duration_days = models.IntegerField(default=14)  # New field
    return_date = models.DateTimeField(null=True, blank=True)
    return_requested_date = models.DateTimeField(null=True, blank=True)  # New field
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrowed')
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.student.name} - {self.book.title}"

    def save(self, *args, **kwargs):
        if not self.due_date:
            self.due_date = timezone.now() + timedelta(days=self.borrow_duration_days)
        super().save(*args, **kwargs)

    def calculate_fine(self):
        """Calculate fine based on overdue days"""
        if self.status == 'returned' and self.return_date:
            if self.return_date > self.due_date:
                days_overdue = (self.return_date - self.due_date).days
                return days_overdue * 1.0  # RM1 per day
        elif self.status in ['borrowed', 'overdue', 'pending_return']:
            if timezone.now() > self.due_date:
                days_overdue = (timezone.now() - self.due_date).days
                return days_overdue * 1.0
        return 0.0
    
    def days_until_due(self):
        """Calculate days until due date"""
        if self.status in ['borrowed', 'pending_return']:
            delta = self.due_date - timezone.now()
            return delta.days
        return None
    
    def is_overdue(self):
        """Check if book is overdue"""
        return timezone.now() > self.due_date and self.status != 'returned'
    
    def should_warn(self):
        """Check if student should receive warning (within 3 days of due date)"""
        if self.status in ['borrowed', 'pending_return']:
            days_left = self.days_until_due()
            return days_left is not None and 0 <= days_left <= 3
        return False

    class Meta:
        ordering = ['-borrow_date']


class Fine(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    ]

    borrow_record = models.OneToOneField(BorrowRecord, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    paid_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Fine for {self.borrow_record.student.name} - RM{self.amount}"

    class Meta:
        ordering = ['-borrow_record__borrow_date']