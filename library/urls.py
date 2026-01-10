from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # Main pages
    path('', views.home, name='home'),
    path('books/', views.book_list, name='book_list'),
    path('students/', views.student_list, name='student_list'),
    path('students/<int:student_id>/', views.student_detail, name='student_detail'),  # Add this
    path('borrows/', views.borrow_list, name='borrow_list'),
    path('fines/', views.fine_list, name='fine_list'),
    
    # Student dashboard
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    
    # Book management
    path('books/add/', views.add_book, name='add_book'),
    path('books/<int:book_id>/', views.book_detail, name='book_detail'),
    path('books/<int:book_id>/edit/', views.edit_book, name='edit_book'),
    path('books/<int:book_id>/delete/', views.delete_book, name='delete_book'),
    
    # Borrow and Return
    path('books/<int:book_id>/borrow/', views.borrow_book, name='borrow_book'),
    path('borrows/<int:record_id>/request-return/', views.request_return, name='request_return'),
    path('borrows/<int:record_id>/verify-return/', views.verify_return, name='verify_return'),
    path('borrows/<int:record_id>/reject-return/', views.reject_return, name='reject_return'),
    
    # Fine Management
    path('fines/<int:fine_id>/mark-paid/', views.mark_fine_paid, name='mark_fine_paid'),
    path('fines/<int:record_id>/create-and-mark-paid/', views.create_and_mark_fine_paid, name='create_and_mark_fine_paid'),
]