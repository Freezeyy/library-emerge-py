from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from .models import Student, Book, BorrowRecord, Fine
from datetime import timedelta
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Student, Book, BorrowRecord, Fine, UserProfile
from .forms import BookForm, BorrowBookForm, ReturnVerificationForm
from django.db.models import F
from django.db import models

def home(request):
    total_books = Book.objects.count()
    total_students = Student.objects.count()
    borrowed_books = BorrowRecord.objects.filter(status='borrowed').count()
    overdue_books = BorrowRecord.objects.filter(status='overdue').count()
    recent_borrows = BorrowRecord.objects.all()[:5]
    
    context = {
        'total_books': total_books,
        'total_students': total_students,
        'borrowed_books': borrowed_books,
        'overdue_books': overdue_books,
        'recent_borrows': recent_borrows,
    }
    return render(request, 'library/home.html', context)


def book_list(request):
    query = request.GET.get('q', '')
    if query:
        books = Book.objects.filter(
            Q(title__icontains=query) | 
            Q(author__icontains=query) | 
            Q(isbn__icontains=query)
        )
    else:
        books = Book.objects.all()
    
    return render(request, 'library/book_list.html', {'books': books, 'query': query})


@login_required
def student_list(request):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can view student list')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    query = request.GET.get('q', '')
    if query:
        students = Student.objects.filter(
            Q(name__icontains=query) | 
            Q(student_id__icontains=query) | 
            Q(email__icontains=query)
        )
    else:
        students = Student.objects.all()
    
    # Get borrow statistics for each student
    student_data = []
    for student in students:
        borrowed_count = BorrowRecord.objects.filter(
            student=student,
            status__in=['borrowed', 'pending_return', 'overdue']
        ).count()
        
        overdue_count = BorrowRecord.objects.filter(
            student=student,
            status='overdue'
        ).count()
        
        total_fines = Fine.objects.filter(
            borrow_record__student=student,
            status='pending'
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        student_data.append({
            'student': student,
            'borrowed_count': borrowed_count,
            'overdue_count': overdue_count,
            'total_fines': total_fines,
        })
    
    return render(request, 'library/student_list.html', {
        'student_data': student_data,
        'query': query
    })


@login_required
def student_detail(request, student_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can view student details')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    student = get_object_or_404(Student, id=student_id)
    
    # Get all borrow records
    borrow_records = BorrowRecord.objects.filter(student=student).order_by('-borrow_date')
    
    # Get current borrowed books
    current_borrows = borrow_records.filter(status__in=['borrowed', 'pending_return', 'overdue'])
    
    # Get fines
    fines = Fine.objects.filter(borrow_record__student=student)
    pending_fines = fines.filter(status='pending')
    total_pending_fines = pending_fines.aggregate(total=models.Sum('amount'))['total'] or 0
    
    context = {
        'student': student,
        'borrow_records': borrow_records,
        'current_borrows': current_borrows,
        'fines': fines,
        'pending_fines': pending_fines,
        'total_pending_fines': total_pending_fines,
    }
    
    return render(request, 'library/student_detail.html', context)


def borrow_list(request):
    status_filter = request.GET.get('status', '')
    if status_filter:
        records = BorrowRecord.objects.filter(status=status_filter)
    else:
        records = BorrowRecord.objects.all()
    
    return render(request, 'library/borrow_list.html', {'records': records, 'status_filter': status_filter})


def fine_list(request):
    status_filter = request.GET.get('status', '')
    if status_filter:
        fines = Fine.objects.filter(status=status_filter)
    else:
        fines = Fine.objects.all()
    
    return render(request, 'library/fine_list.html', {'fines': fines, 'status_filter': status_filter})


# Authentication Views
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            
            # Redirect based on role
            try:
                profile = UserProfile.objects.get(user=user)
                if profile.role == 'librarian':
                    return redirect('home')
                else:
                    return redirect('student_dashboard')
            except UserProfile.DoesNotExist:
                return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'library/login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        student_id = request.POST.get('student_id')
        name = request.POST.get('name')
        phone = request.POST.get('phone')
        
        # Validation
        if password != password2:
            messages.error(request, 'Passwords do not match')
            return render(request, 'library/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'library/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return render(request, 'library/register.html')
        
        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = name
        user.save()
        
        # Create user profile
        UserProfile.objects.create(user=user, role='student', phone=phone)
        
        # Create student record
        Student.objects.create(
            user=user,
            student_id=student_id,
            name=name,
            email=email,
            phone=phone
        )
        
        messages.success(request, 'Registration successful! Please login.')
        return redirect('login')
    
    return render(request, 'library/register.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'You have been logged out successfully')
    return redirect('login')


@login_required
def student_dashboard(request):
    try:
        student = Student.objects.get(user=request.user)
        borrowed_books = BorrowRecord.objects.filter(student=student, status__in=['borrowed', 'overdue', 'pending_return'])
        borrow_history = BorrowRecord.objects.filter(student=student).order_by('-borrow_date')
        
        # Get existing fines from database
        fines = Fine.objects.filter(borrow_record__student=student, status='pending')
        
        # Calculate total fines including current overdue books
        total_fines = 0
        
        # Add fines from Fine table
        for fine in fines:
            total_fines += float(fine.amount)
        
        # Add calculated fines for currently overdue books (not yet in Fine table)
        for record in borrowed_books:
            if record.is_overdue():
                # Check if fine already exists for this record
                existing_fine = Fine.objects.filter(borrow_record=record).first()
                if not existing_fine:
                    total_fines += record.calculate_fine()
        
        context = {
            'student': student,
            'borrowed_books': borrowed_books,
            'borrow_history': borrow_history,
            'fines': fines,
            'total_fines': total_fines,
        }
        return render(request, 'library/student_dashboard.html', context)
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found')
        return redirect('home')
    

    # Book Management Views (Librarian only)
@login_required
def add_book(request):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can add books')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            # Auto-generate ISBN or use a simple counter
            import random
            book.isbn = f"BK{random.randint(100000, 999999)}"
            book.total_copies = 1
            book.available_copies = 1
            book.save()
            messages.success(request, f'Book "{book.title}" added successfully!')
            return redirect('book_list')
    else:
        form = BookForm()
    
    return render(request, 'library/add_book.html', {'form': form})


@login_required
def edit_book(request, book_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can edit books')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        form = BookForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            book = form.save()
            messages.success(request, f'Book "{book.title}" updated successfully!')
            return redirect('book_list')
    else:
        form = BookForm(instance=book)
    
    return render(request, 'library/edit_book.html', {'form': form, 'book': book})


@login_required
def delete_book(request, book_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can delete books')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    book = get_object_or_404(Book, id=book_id)
    
    if request.method == 'POST':
        title = book.title
        book.delete()
        messages.success(request, f'Book "{title}" deleted successfully!')
        return redirect('book_list')
    
    return render(request, 'library/delete_book.html', {'book': book})


@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    return render(request, 'library/book_detail.html', {'book': book})


# Borrow and Return System
@login_required
def borrow_book(request, book_id):
    # Check if user is student
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'student':
            messages.error(request, 'Only students can borrow books')
            return redirect('book_detail', book_id=book_id)
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('book_detail', book_id=book_id)
    
    book = get_object_or_404(Book, id=book_id)
    student = get_object_or_404(Student, user=request.user)
    
    # Check if book is available
    if book.available_copies <= 0:
        messages.error(request, 'This book is currently not available')
        return redirect('book_detail', book_id=book_id)
    
    # Check if student already borrowed this book and hasn't returned it
    existing_borrow = BorrowRecord.objects.filter(
        student=student,
        book=book,
        status__in=['borrowed', 'pending_return', 'overdue']
    ).first()
    
    if existing_borrow:
        messages.error(request, 'You have already borrowed this book')
        return redirect('book_detail', book_id=book_id)
    
    # Check if student has any overdue books
    overdue_books = BorrowRecord.objects.filter(
        student=student,
        status='overdue'
    )
    
    if overdue_books.exists():
        messages.error(request, 'You have overdue books. Please return them before borrowing new books.')
        return redirect('student_dashboard')
    
    if request.method == 'POST':
        form = BorrowBookForm(request.POST)
        if form.is_valid():
            borrow_record = form.save(commit=False)
            borrow_record.student = student
            borrow_record.book = book
            borrow_record.borrow_date = timezone.now()
            borrow_record.due_date = timezone.now() + timedelta(days=form.cleaned_data['borrow_duration_days'])
            borrow_record.status = 'borrowed'
            borrow_record.save()
            
            # Decrease available copies
            book.available_copies = F('available_copies') - 1
            book.save()
            book.refresh_from_db()
            
            messages.success(request, f'Successfully borrowed "{book.title}"! Due date: {borrow_record.due_date.strftime("%B %d, %Y")}')
            return redirect('student_dashboard')
    else:
        form = BorrowBookForm(initial={'borrow_duration_days': 14})
    
    return render(request, 'library/borrow_book.html', {
        'form': form,
        'book': book,
    })


@login_required
def request_return(request, record_id):
    # Check if user is student
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'student':
            messages.error(request, 'Access denied')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    student = get_object_or_404(Student, user=request.user)
    record = get_object_or_404(BorrowRecord, id=record_id, student=student)
    
    if record.status != 'borrowed' and record.status != 'overdue':
        messages.error(request, 'This book cannot be returned')
        return redirect('student_dashboard')
    
    record.status = 'pending_return'
    record.return_requested_date = timezone.now()
    record.save()
    
    messages.success(request, f'Return request submitted for "{record.book.title}". Please bring the book to the library for verification.')
    return redirect('student_dashboard')


@login_required
def verify_return(request, record_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can verify returns')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    record = get_object_or_404(BorrowRecord, id=record_id)
    
    if record.status != 'pending_return':
        messages.error(request, 'This book is not pending return')
        return redirect('borrow_list')
    
    if request.method == 'POST':
        form = ReturnVerificationForm(request.POST)
        if form.is_valid():
            # Mark as returned
            record.status = 'returned'
            record.return_date = timezone.now()
            
            # Add librarian notes
            condition = form.cleaned_data['condition']
            librarian_notes = form.cleaned_data['librarian_notes']
            record.notes = f"Condition: {condition}\nLibrarian Notes: {librarian_notes}"
            record.save()
            
            # Increase available copies
            book = record.book
            book.available_copies = F('available_copies') + 1
            book.save()
            book.refresh_from_db()
            
            # Create fine if overdue
            fine_amount = record.calculate_fine()
            if fine_amount > 0:
                Fine.objects.create(
                    borrow_record=record,
                    amount=fine_amount,
                    status='pending'
                )
                messages.warning(request, f'Book returned. Fine of RM{fine_amount:.2f} has been added for late return.')
            else:
                messages.success(request, f'Book "{record.book.title}" returned successfully!')
            
            return redirect('borrow_list')
    else:
        form = ReturnVerificationForm()
    
    return render(request, 'library/verify_return.html', {
        'form': form,
        'record': record,
    })


@login_required
def reject_return(request, record_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can reject returns')
            return redirect('home')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('home')
    
    record = get_object_or_404(BorrowRecord, id=record_id)
    
    if record.status != 'pending_return':
        messages.error(request, 'This book is not pending return')
        return redirect('borrow_list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        record.status = 'overdue' if record.is_overdue() else 'borrowed'
        record.return_requested_date = None
        record.notes = f"Return rejected. Reason: {reason}"
        record.save()
        
        messages.warning(request, f'Return request rejected for "{record.book.title}".')
        return redirect('borrow_list')
    
    return render(request, 'library/reject_return.html', {'record': record})