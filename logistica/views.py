from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.db.models import Sum, Count
from .models import MaterialDescarte
from .forms import MaterialDescarteForm

import csv
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def home(request):
    # Contagem de registros distintos por unidade/setor
    total_registros = MaterialDescarte.objects.values('unidade').distinct().count()
    
    # Soma total de todos os equipamentos/itens entregues
    total_itens = MaterialDescarte.objects.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    
    # Dados para o Gráfico de Categorias (Chart.js)
    dados_grafico = MaterialDescarte.objects.values('categoria').annotate(total=Sum('quantidade'))
    
    # Mapeamento para nomes amigáveis no gráfico
    choices_dict = dict(MaterialDescarteForm().fields['categoria'].choices)
    labels = [choices_dict.get(item['categoria'], item['categoria']) for item in dados_grafico]
    totais = [item['total'] for item in dados_grafico]

    context = {
        'total_registros': total_registros, # Exibe a quantidade de Unidades atendidas
        'total_itens': total_itens,
        'chart_labels': labels,
        'chart_data': totais,
    }
    return render(request, 'logistica/home.html', context)

def dashboard(request):
    descartes = MaterialDescarte.objects.all().order_by('-data_registro')
    
    # Filtro de Busca por Unidade ou Categoria
    busca = request.GET.get('busca')
    if busca:
        descartes = descartes.filter(unidade__icontains=busca) | descartes.filter(modelo__icontains=busca) | descartes.filter(categoria__icontains=busca)

    return render(request, 'logistica/dashboard.html', {'descartes': descartes, 'busca': busca})

def exportar_csv(request):
    """ Exporta os registros do banco de dados para um arquivo CSV/Excel """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="relatorio_geral_ufpa_{datetime.now().strftime("%Y%m%d_%H%M")}.csv"'
    response.write(u'\ufeff'.encode('utf8')) # UTF-8 BOM para o Excel abrir sem acentos quebrados

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['ID', 'Unidade/Setor', 'Categoria', 'Modelo/Descrição', 'Quantidade', 'Data de Registro'])

    choices_dict = dict(MaterialDescarteForm().fields['categoria'].choices)

    for item in MaterialDescarte.objects.all().order_by('-data_registro'):
        writer.writerow([
            item.id,
            item.unidade,
            choices_dict.get(item.categoria, item.categoria),
            item.modelo,
            item.quantidade,
            item.data_registro.strftime('%d/%m/%Y %H:%M')
        ])

    return response

def remover_item_sessao(request, index):
    """ Remove um item específico da lista temporária antes de gerar o PDF """
    if 'lista_materiais' in request.session:
        lista = request.session['lista_materiais']
        if 0 <= index < len(lista):
            removido = lista.pop(index)
            request.session['lista_materiais'] = lista
            messages.warning(request, f"Item '{removido['modelo']}' removido da lista.")
    return redirect('registrar_material')

def registrar_material(request):
    if 'lista_materiais' not in request.session:
        request.session['lista_materiais'] = []

    if request.method == 'POST':
        if 'adicionar_item' in request.POST:
            form = MaterialDescarteForm(request.POST)
            if form.is_valid():
                item_dados = {
                    'unidade': form.cleaned_data['unidade'],
                    'categoria': form.cleaned_data['categoria'],
                    'categoria_exibicao': dict(form.fields['categoria'].choices)[form.cleaned_data['categoria']],
                    'modelo': form.cleaned_data['modelo'],
                    'quantidade': form.cleaned_data['quantidade'],
                }
                lista = request.session['lista_materiais']
                lista.append(item_dados)
                request.session['lista_materiais'] = lista
                messages.success(request, f"Item '{item_dados['modelo']}' adicionado com sucesso!")
                form = MaterialDescarteForm(initial={'unidade': item_dados['unidade']})
                
        elif 'finalizar_registro' in request.POST:
            lista = request.session.get('lista_materiais', [])
            
            if lista:
                for item in lista:
                    MaterialDescarte.objects.create(
                        unidade=item['unidade'],
                        categoria=item['categoria'],
                        modelo=item['modelo'],
                        quantidade=item['quantidade']
                    )
                
                # PDF Generation
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="guia_descarte_ufpa_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
                
                doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
                story = []
                styles = getSampleStyleSheet()
                
                BORDÔ_RIPAT = colors.HexColor('#4A1525')
                CINZA_TEXTO = colors.HexColor('#334155')
                CINZA_CLARO = colors.HexColor('#f8fafc')
                LINHA_GRID = colors.HexColor('#e2e8f0')
                
                title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=BORDÔ_RIPAT, alignment=1)
                subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, textColor=CINZA_TEXTO, alignment=1)
                normal_style = ParagraphStyle('DocNormal', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=15, textColor=CINZA_TEXTO)
                header_table_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.white)
                table_cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14, textColor=CINZA_TEXTO)
                style_assinatura = ParagraphStyle('DocSignature', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=14, textColor=CINZA_TEXTO, alignment=1)
                
                story.append(Paragraph("UNIVERSIDADE FEDERAL DO PARÁ", title_style))
                story.append(Paragraph("SISTEMA DE LOGÍSTICA REVERSA DE RESÍDUOS TECNOLÓGICOS", subtitle_style))
                story.append(Paragraph(f"Guia de Entrega de Materiais - Gerada em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", subtitle_style))
                story.append(Spacer(1, 20))
                
                unidade_origem = lista[0]['unidade']
                story.append(Paragraph(f"<b>Unidade/Setor de Origem:</b> {unidade_origem}", normal_style))
                story.append(Paragraph("<b>Instruções:</b> Imprima este relatório e apresente-o assinado junto com os itens físicos no local de coleta.", normal_style))
                story.append(Spacer(1, 20))
                
                dados_tabela = [[Paragraph("Categoria", header_table_style), Paragraph("Modelo / Descrição", header_table_style), Paragraph("Qtd", header_table_style)]]
                
                for item in lista:
                    dados_tabela.append([
                        Paragraph(item['categoria_exibicao'], table_cell_style),
                        Paragraph(item['modelo'], table_cell_style),
                        Paragraph(str(item['quantidade']), table_cell_style)
                    ])
                
                tabela = Table(dados_tabela, colWidths=[150, 310, 50])
                tabela.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), BORDÔ_RIPAT),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('TOPPADDING', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                    ('LINEBELOW', (0,0), (-1,-1), 0.5, LINHA_GRID),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_CLARO])
                ]))
                story.append(tabela)
                story.append(Spacer(1, 50))
                
                coluna_esquerda = Paragraph("____________________________________________<br/><br/>Assinatura do Responsável pelo Envio<br/>(Origem)", style_assinatura)
                coluna_direita = Paragraph("____________________________________________<br/><br/>Assinatura do Recebedor<br/>(Unidade de Logística Reversa)", style_assinatura)
                
                tabela_assinaturas = Table([[coluna_esquerda, coluna_direita]], colWidths=[255, 255])
                tabela_assinaturas.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
                story.append(tabela_assinaturas)
                
                doc.build(story)
                request.session['lista_materiais'] = []
                return response
            else:
                return redirect('home')
    else:
        form = MaterialDescarteForm()

    context = {
        'form': form,
        'lista_temporaria': request.session['lista_materiais']
    }
    return render(request, 'logistica/registrar.html', context)