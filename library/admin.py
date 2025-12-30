from django.contrib import admin
from .models import Student, Book, BorrowRecord, Fine, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'phone']
    list_filter = ['role']

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'name', 'email', 'phone']
    search_fields = ['student_id', 'name', 'email']

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['isbn', 'title', 'author', 'category', 'available_copies', 'total_copies']
    search_fields = ['isbn', 'title', 'author']
    list_filter = ['category']

@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ['student', 'book', 'borrow_date', 'due_date', 'return_date', 'status']
    list_filter = ['status', 'borrow_date']
    search_fields = ['student__name', 'book__title']

@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ['borrow_record', 'amount', 'status', 'paid_date']
    list_filter = ['status']