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

def index(request):
    """Root URL handler - redirects to appropriate page based on authentication and role"""
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.role == 'librarian':
                return redirect('home')
            else:
                return redirect('student_dashboard')
        except UserProfile.DoesNotExist:
            return redirect('login')
    else:
        return redirect('login')

@login_required
def home(request):
    # Check if user is librarian - only librarians can access home page
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.info(request, 'Redirected to your dashboard')
            return redirect('student_dashboard')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('login')
    
    # Update overdue statuses for books that are past due date
    # This ensures the status is current when displaying the home page
    overdue_records = BorrowRecord.objects.filter(
        status__in=['borrowed', 'pending_return'],
        due_date__lt=timezone.now()
    ).exclude(status='returned')
    
    # Update status to overdue (this will trigger the save() method which handles the logic)
    for record in overdue_records:
        if record.status != 'pending_return':  # Don't change pending_return status
            record.status = 'overdue'
            record.save(update_fields=['status'])
    
    total_books = Book.objects.count()
    total_students = Student.objects.count()
    # Count all books that are currently borrowed (not returned yet)
    # This includes 'borrowed', 'overdue', and 'pending_return' statuses
    borrowed_books = BorrowRecord.objects.filter(
        status__in=['borrowed', 'overdue', 'pending_return']
    ).exclude(status='returned').count()
    
    # Count overdue books: due_date has passed and status is not 'returned'
    overdue_books = BorrowRecord.objects.filter(
        status__in=['borrowed', 'overdue', 'pending_return'],
        due_date__lt=timezone.now()
    ).exclude(status='returned').count()
    
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
    if status_filter == 'currently_borrowed':
        # Show all books that are currently borrowed (not returned yet)
        records = BorrowRecord.objects.filter(
            status__in=['borrowed', 'overdue', 'pending_return']
        ).exclude(status='returned')
    elif status_filter:
        records = BorrowRecord.objects.filter(status=status_filter)
    else:
        records = BorrowRecord.objects.all()
    
    return render(request, 'library/borrow_list.html', {'records': records, 'status_filter': status_filter})


@login_required
def fine_list(request):
    # Check if user is librarian
    is_librarian = False
    try:
        profile = UserProfile.objects.get(user=request.user)
        is_librarian = (profile.role == 'librarian')
    except UserProfile.DoesNotExist:
        pass
    
    status_filter = request.GET.get('status', '')
    
    # Get all existing fines from database
    if status_filter:
        existing_fines = Fine.objects.filter(status=status_filter)
    else:
        existing_fines = Fine.objects.all()
    
    # Get all overdue books that don't have a Fine record yet
    overdue_records = BorrowRecord.objects.filter(
        status__in=['overdue', 'borrowed', 'pending_return']
    ).exclude(
        id__in=existing_fines.values_list('borrow_record_id', flat=True)
    )
    
    # Filter overdue records that actually have fines
    overdue_with_fines = []
    for record in overdue_records:
        fine_amount = record.calculate_fine()
        if fine_amount > 0:
            overdue_with_fines.append({
                'borrow_record': record,
                'amount': fine_amount,
                'status': 'pending',
                'is_calculated': True,  # Flag to indicate this is calculated, not in DB
            })
    
    # Combine existing fines with calculated fines
    all_fines = []
    total_amount = 0
    
    for fine in existing_fines:
        record = fine.borrow_record
        # Calculate days overdue using the model method
        days_overdue = record.days_overdue()
        
        fine_amount = float(fine.amount)
        total_amount += fine_amount
        
        all_fines.append({
            'borrow_record': record,
            'amount': fine_amount,
            'status': fine.status,
            'paid_date': fine.paid_date,
            'is_calculated': False,
            'days_overdue': days_overdue,
            'fine_id': fine.id,  # Add fine_id for existing fines
        })
    
    # Add calculated fines
    for fine_data in overdue_with_fines:
        record = fine_data['borrow_record']
        # Calculate days overdue using the model method
        days_overdue = record.days_overdue()
        
        fine_amount = fine_data['amount']
        total_amount += fine_amount
        
        all_fines.append({
            'borrow_record': record,
            'amount': fine_amount,
            'status': fine_data['status'],
            'paid_date': None,
            'is_calculated': True,
            'days_overdue': days_overdue,
            'fine_id': None,  # No fine_id for calculated fines (not in DB yet)
        })
    
    # Sort by borrow date (most recent first)
    all_fines.sort(key=lambda x: x['borrow_record'].borrow_date, reverse=True)
    
    # Apply status filter if specified
    if status_filter:
        all_fines = [f for f in all_fines if f['status'] == status_filter]
        # Recalculate total for filtered fines
        total_amount = sum(f['amount'] for f in all_fines)
    
    return render(request, 'library/fine_list.html', {
        'fines': all_fines,
        'status_filter': status_filter,
        'total_amount': total_amount,
        'total_count': len(all_fines),
        'is_librarian': is_librarian,
    })


@login_required
def mark_fine_paid(request, fine_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can mark fines as paid')
            return redirect('fine_list')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('fine_list')
    
    fine = get_object_or_404(Fine, id=fine_id)
    
    if request.method == 'POST':
        fine.status = 'paid'
        fine.paid_date = timezone.now()
        fine.save()
        messages.success(request, f'Fine of RM{fine.amount:.2f} marked as paid successfully!')
        return redirect('fine_list')
    
    return render(request, 'library/mark_fine_paid.html', {'fine': fine})


@login_required
def create_and_mark_fine_paid(request, record_id):
    # Check if user is librarian
    try:
        profile = UserProfile.objects.get(user=request.user)
        if profile.role != 'librarian':
            messages.error(request, 'Only librarians can mark fines as paid')
            return redirect('fine_list')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Access denied')
        return redirect('fine_list')
    
    record = get_object_or_404(BorrowRecord, id=record_id)
    
    if request.method == 'POST':
        # Calculate fine amount
        fine_amount = record.calculate_fine()
        
        if fine_amount > 0:
            # Check if fine already exists
            fine, created = Fine.objects.get_or_create(
                borrow_record=record,
                defaults={
                    'amount': fine_amount,
                    'status': 'paid',  # Mark as paid immediately
                    'paid_date': timezone.now()
                }
            )
            
            if not created:
                # Fine already exists, just update it
                fine.status = 'paid'
                fine.paid_date = timezone.now()
                fine.save()
            
            messages.success(request, f'Fine of RM{fine_amount:.2f} created and marked as paid successfully!')
        else:
            messages.warning(request, 'No fine amount to record.')
        
        return redirect('fine_list')
    
    # Calculate fine for display
    fine_amount = record.calculate_fine()
    return render(request, 'library/mark_fine_paid.html', {
        'record': record,
        'fine_amount': fine_amount,
        'is_calculated': True
    })


# Authentication Views
def login_view(request):
    # If user is already logged in, redirect them based on role
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.role == 'librarian':
                return redirect('home')
            else:
                return redirect('student_dashboard')
        except UserProfile.DoesNotExist:
            return redirect('home')
    
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
        role = request.POST.get('role', 'student')  # Default to student if not provided
        name = request.POST.get('name')
        phone = request.POST.get('phone', '')
        student_id = request.POST.get('student_id', '')
        
        # Validation
        if password != password2:
            messages.error(request, 'Passwords do not match')
            return render(request, 'library/register.html', {'role': role})
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists')
            return render(request, 'library/register.html', {'role': role})
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists')
            return render(request, 'library/register.html', {'role': role})
        
        # Role-specific validation
        if role == 'student':
            if not student_id:
                messages.error(request, 'Student ID is required for student registration')
                return render(request, 'library/register.html', {'role': role})
            if Student.objects.filter(student_id=student_id).exists():
                messages.error(request, 'Student ID already exists')
                return render(request, 'library/register.html', {'role': role})
        
        # Create user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.first_name = name
        user.save()
        
        # Create user profile with selected role
        UserProfile.objects.create(user=user, role=role, phone=phone)
        
        # Create student record only if role is student
        if role == 'student':
            Student.objects.create(
                user=user,
                student_id=student_id,
                name=name,
                email=email,
                phone=phone
            )
        
        messages.success(request, f'Registration successful! You can now login as {role}.')
        return redirect('login')
    
    return render(request, 'library/register.html')


def logout_view(request):
    logout(request)
    # Clear any existing messages and set only the logout message
    list(messages.get_messages(request))  # Consume all existing messages
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
    
    # Check if user is student and has overdue books
    has_overdue = False
    overdue_count = 0
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.role == 'student':
                student = Student.objects.get(user=request.user)
                overdue_books = BorrowRecord.objects.filter(
                    student=student,
                    status='overdue'
                )
                overdue_count = overdue_books.count()
                has_overdue = overdue_count > 0
        except (UserProfile.DoesNotExist, Student.DoesNotExist):
            pass
    
    return render(request, 'library/book_detail.html', {
        'book': book,
        'has_overdue': has_overdue,
        'overdue_count': overdue_count,
    })


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
        overdue_count = overdue_books.count()
        messages.error(
            request, 
            f'⚠️ You have {overdue_count} overdue book(s). Please return them before borrowing new books. Go to your dashboard to see details.'
        )
        return redirect('book_detail', book_id=book_id)
    
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
            
            # Create fine if overdue (only if fine doesn't already exist)
            fine_amount = record.calculate_fine()
            if fine_amount > 0:
                fine, created = Fine.objects.get_or_create(
                    borrow_record=record,
                    defaults={
                        'amount': fine_amount,
                        'status': 'pending'
                    }
                )
                # If fine already exists, update the amount in case it changed (but don't change status if already paid)
                if not created and fine.status == 'pending':
                    fine.amount = fine_amount
                    fine.save()
                
                if created:
                    messages.warning(request, f'Book returned. Fine of RM{fine_amount:.2f} has been added for late return.')
                else:
                    messages.warning(request, f'Book returned. Fine of RM{fine_amount:.2f} already exists for this return.')
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