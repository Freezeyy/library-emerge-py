from django import forms
from .models import Book, Student, BorrowRecord

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'author', 'publisher', 'category', 'description', 'cover_image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter book title'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter author name'}),
            'publisher': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter publisher'}),
            'category': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Fiction, Science, History'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Optional: Enter book description'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
        }
        
    def clean(self):
        cleaned_data = super().clean()
        total_copies = cleaned_data.get('total_copies')
        available_copies = cleaned_data.get('available_copies')
        
        if available_copies and total_copies:
            if available_copies > total_copies:
                raise forms.ValidationError('Available copies cannot be more than total copies')
        
        return cleaned_data
    

class BorrowBookForm(forms.ModelForm):
    class Meta:
        model = BorrowRecord
        fields = ['borrow_duration_days', 'notes']
        widgets = {
            'borrow_duration_days': forms.Select(
                choices=[(7, '1 Week (7 days)'), (14, '2 Weeks (14 days)')],
                attrs={'class': 'form-control'}
            ),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional: Add any notes about this borrowing'
            }),
        }
        labels = {
            'borrow_duration_days': 'Borrow Duration',
            'notes': 'Notes (Optional)',
        }


class ReturnVerificationForm(forms.Form):
    condition = forms.ChoiceField(
        choices=[
            ('good', 'Good Condition'),
            ('damaged', 'Damaged'),
            ('lost', 'Lost'),
        ],
        widget=forms.RadioSelect,
        label='Book Condition'
    )
    librarian_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add notes about the book condition or any issues'
        }),
        required=False,
        label='Librarian Notes'
    )