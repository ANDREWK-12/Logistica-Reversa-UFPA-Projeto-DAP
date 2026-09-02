from django import forms
from .models import MaterialDescarte

class MaterialDescarteForm(forms.ModelForm):
    class Meta:
        model = MaterialDescarte
        fields = ['unidade', 'categoria', 'modelo', 'quantidade']
        
        widgets = {
            
            'unidade': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'on'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }