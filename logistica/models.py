# logistica/models.py
from django.db import models

class MaterialDescarte(models.Model):
    CATEGORIAS_CHOICES = [
        ('toner', 'Toner'),
        ('unidade_imagem', 'Unidade de Imagem'),
        ('cartucho', 'Cartucho'),
        ('periferico', 'Periférico de Informática (Mouse, Teclado, etc.)'),
        ('armazenamento', 'Unidade de Armazenamento (HD, SSD)'),
        ('pilha', 'Pilha'),
        ('bateria_nobreak', 'Bateria de Nobreak'),
        ('lampada', 'Lâmpada'),
    ]

    STATUS_CHOICES = [
        ('pendente', 'Pendente de Envio'),
        ('recebido', 'Recebido na Triagem'),
        ('descartado', 'Descartado Corretamente'),
    ]

    # Agora o usuário digita a unidade livremente (ex: "ICEN", "Laboratório X de Engenharia")
    unidade = models.CharField(max_length=100, verbose_name="Unidade da UFPA / Setor")
    categoria = models.CharField(max_length=30, choices=CATEGORIAS_CHOICES, verbose_name="Categoria do Material")
    modelo = models.CharField(max_length=100, verbose_name="Modelo / Descrição do Material")
    quantidade = models.PositiveIntegerField(verbose_name="Quantidade")
    data_registro = models.DateTimeField(auto_now_add=True, verbose_name="Data de Registro")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente', verbose_name="Status do Descarte")

    def __str__(self):
        return f"{self.get_categoria_display()} - {self.modelo} ({self.unidade})"