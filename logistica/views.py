from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.conf import settings
from django.db.models import Q, Sum
from .models import MaterialDescarte
from .forms import MaterialDescarteForm

import csv
import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.utils import timezone

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
    
    # 1. Filtros da Busca
    busca = request.GET.get('busca', '')
    unidade_filtro = request.GET.get('unidade', '')
    categoria_filtro = request.GET.get('categoria', '')

    if busca:
        descartes = descartes.filter(
            Q(unidade__icontains=busca)
            | Q(modelo__icontains=busca)
            | Q(categoria__icontains=busca)
        )

    if unidade_filtro:
        descartes = descartes.filter(unidade=unidade_filtro)

    if categoria_filtro:
        descartes = descartes.filter(categoria=categoria_filtro)

    # 2. Dados para Métricas Rápidas
    total_itens = descartes.aggregate(Sum('quantidade'))['quantidade__sum'] or 0
    total_unidades = descartes.values('unidade').distinct().count()

    # 3. Lista de Unidades Únicas para o filtro Dropdown
    lista_unidades = MaterialDescarte.objects.values_list('unidade', flat=True).distinct().order_by('unidade')

    # 4. Dados para Gráfico 1: Itens por Categoria
    categorias_query = descartes.values('categoria').annotate(
        total=Sum('quantidade')
    ).order_by('categoria')
    choices_dict = dict(MaterialDescarteForm().fields['categoria'].choices)
    
    cat_labels = [choices_dict.get(item['categoria'], item['categoria']) for item in categorias_query]
    cat_totais = [item['total'] for item in categorias_query]

    # 5. Dados para Gráfico 2: Top Unidades que mais entregaram
    unidades_query = descartes.values('unidade').annotate(total=Sum('quantidade')).order_by('-total')[:5]
    uni_labels = [item['unidade'] for item in unidades_query]
    uni_totais = [item['total'] for item in unidades_query]

    context = {
        'descartes': descartes,
        'busca': busca,
        'unidade_filtro': unidade_filtro,
        'categoria_filtro': categoria_filtro,
        'lista_categorias': MaterialDescarte.CATEGORIAS_CHOICES,
        'lista_unidades': lista_unidades,
        'total_itens': total_itens,
        'total_unidades': total_unidades,
        'cat_labels': cat_labels,
        'cat_data': cat_totais,
        'uni_labels': uni_labels,
        'uni_data': uni_totais,
    }
    return render(request, 'logistica/dashboard.html', context)

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

def gerar_relatorio_entrega(lista):
    page_size = landscape(A4)
    page_width, page_height = page_size
    margin = 34
    content_width = page_width - 2 * margin
    asset_dir = Path(settings.BASE_DIR) / 'media' / 'relatorio_visual'
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=100,
        bottomMargin=62,
    )
    styles = getSampleStyleSheet()
    verde = colors.HexColor('#1D7448')
    verde_escuro = colors.HexColor('#155C38')
    verde_claro = colors.HexColor('#EFF7F1')
    bordô = colors.HexColor('#4A1525')
    texto = colors.HexColor('#334155')
    texto_suave = colors.HexColor('#64748B')
    cinza_claro = colors.HexColor('#F8FAFC')
    linha = colors.HexColor('#D7E0E7')

    titulo_style = ParagraphStyle(
        'RelatorioTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=17,
        textColor=bordô,
        alignment=1,
        spaceAfter=4,
    )
    normal_style = ParagraphStyle(
        'RelatorioNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=texto,
    )
    label_style = ParagraphStyle(
        'RelatorioLabel',
        parent=normal_style,
        fontName='Helvetica-Bold',
    )
    section_style = ParagraphStyle(
        'RelatorioSection',
        parent=normal_style,
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.white,
    )
    header_style = ParagraphStyle(
        'RelatorioTableHeader',
        parent=normal_style,
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=11,
        textColor=colors.white,
        alignment=1,
    )
    cell_style = ParagraphStyle(
        'RelatorioTableCell',
        parent=normal_style,
        fontSize=10,
        leading=12,
    )
    category_style = ParagraphStyle(
        'RelatorioCategory',
        parent=cell_style,
        fontName='Helvetica-Bold',
        textColor=verde_escuro,
    )
    quantity_style = ParagraphStyle(
        'RelatorioQuantity',
        parent=cell_style,
        fontName='Helvetica-Bold',
        alignment=1,
    )
    signature_style = ParagraphStyle(
        'RelatorioSignature',
        parent=normal_style,
        alignment=1,
        textColor=texto_suave,
    )
    total_style = ParagraphStyle(
        'RelatorioTotal',
        parent=header_style,
        alignment=2,
    )
    date_text = timezone.localdate().strftime('%d/%m/%Y')
    categorias = MaterialDescarte.CATEGORIAS_CHOICES

    def desenhar_identidade_visual(canvas, _doc):
        canvas.saveState()
        canvas.setFillColor(verde)
        canvas.rect(0, page_height - 8, page_width, 8, stroke=0, fill=1)

        logo_x = page_width * 0.15
        logo_y = page_height - 52
        for filename, center_x, max_width, max_height, center_y in [
            ('logo_logistica_reversa_com_mascote.png', logo_x, 78, 76, logo_y),
            ('image1.jpeg', page_width - logo_x, 78, 76, logo_y),
        ]:
            image = ImageReader(str(asset_dir / filename))
            image_width, image_height = image.getSize()
            scale = min(max_width / image_width, max_height / image_height)
            width = image_width * scale
            height = image_height * scale
            canvas.drawImage(
                image,
                center_x - width / 2,
                center_y - height / 2,
                width=width,
                height=height,
                mask='auto',
            )

        canvas.setFillColor(verde_escuro)
        canvas.setFont('Helvetica-Bold', 14)
        canvas.drawCentredString(page_width / 2, page_height - 43, 'LOGÍSTICA REVERSA')
        canvas.setFillColor(texto_suave)
        canvas.setFont('Helvetica', 9.5)
        canvas.drawCentredString(page_width / 2, page_height - 57, 'UNIVERSIDADE FEDERAL DO PARÁ')

        canvas.setStrokeColor(colors.HexColor('#cbd5e1'))
        canvas.setLineWidth(0.7)
        canvas.line(margin, 52, page_width - margin, 52)
        footer_y = 29
        for filename, center_x in [
            ('image6.png', page_width * 0.22),
            ('image4.png', page_width * 0.5),
            ('image5.png', page_width * 0.78),
        ]:
            image = ImageReader(str(asset_dir / filename))
            image_width, image_height = image.getSize()
            scale = min(185 / image_width, 31 / image_height)
            width = image_width * scale
            height = image_height * scale
            canvas.drawImage(
                image,
                center_x - width / 2,
                footer_y - height / 2,
                width=width,
                height=height,
                mask='auto',
            )
        canvas.setFillColor(texto_suave)
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(page_width - margin, 12, f'Página {_doc.page}')
        canvas.restoreState()

    unidades = {}
    for item in lista:
        unidades.setdefault(item['unidade'], []).append(item)

    story = []
    for unidade_index, (unidade, itens_unidade) in enumerate(unidades.items()):
        if unidade_index:
            story.append(PageBreak())

        story.extend([
            Paragraph(
                'RELATÓRIO DE ENTREGAS DE MATERIAIS DA LOGÍSTICA REVERSA DA UFPA',
                titulo_style,
            ),
            Paragraph(
                'Formulário de entrega para registro e quantificação dos materiais, '
                'conforme a Política Nacional de Resíduos Sólidos (Lei nº 12.305/2010).',
                normal_style,
            ),
            Spacer(1, 9),
        ])

        dados_identificacao = [[
            Paragraph('IDENTIFICAÇÃO DA UNIDADE', section_style),
            '',
            '',
            '',
        ]]
        dados_identificacao = [
            *dados_identificacao,
            [
                Paragraph('Unidade Gestora:', label_style),
                Paragraph(escape(unidade), normal_style),
                Paragraph('Data:', label_style),
                Paragraph(date_text, normal_style),
            ],
            [
                Paragraph('Servidor responsável:', label_style),
                Paragraph(' ', normal_style),
                Paragraph('Contato (telefone/e-mail):', label_style),
                Paragraph(' ', normal_style),
            ],
            [
                Paragraph('Local de Entrega:', label_style),
                Paragraph('Térreo do prédio da PROAD', normal_style),
                '',
                '',
            ],
        ]
        tabela_identificacao = Table(
            dados_identificacao,
            colWidths=[
                content_width * 0.2,
                content_width * 0.34,
                content_width * 0.2,
                content_width * 0.26,
            ],
        )
        tabela_identificacao.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), verde_escuro),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, linha),
            ('BACKGROUND', (0, 1), (0, -1), cinza_claro),
            ('BACKGROUND', (2, 1), (2, 2), cinza_claro),
            ('SPAN', (1, 3), (3, 3)),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.extend([tabela_identificacao, Spacer(1, 8)])

        dados_tabela = [[
            Paragraph('MATERIAIS ENTREGUES', section_style),
            '',
            '',
        ], [
            Paragraph('CATEGORIA', header_style),
            Paragraph('REFERÊNCIA / MODELO', header_style),
            Paragraph('QUANTIDADE<br/>ENTREGUE', header_style),
        ]]
        estilo_tabela = [
            ('SPAN', (0, 0), (2, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), verde_escuro),
            ('BACKGROUND', (0, 1), (-1, 1), bordô),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 1), (-1, -1), 0.45, linha),
            ('ALIGN', (2, 1), (2, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]
        itens_por_categoria = {}
        for item in itens_unidade:
            itens_por_categoria.setdefault(item['categoria'], []).append(item)

        for categoria, rotulo in categorias:
            itens_categoria = itens_por_categoria.get(categoria, [])
            if not itens_categoria:
                continue

            linha_inicio = len(dados_tabela)
            for item_index, item in enumerate(itens_categoria):
                dados_tabela.append([
                    Paragraph(escape(rotulo), category_style) if item_index == 0 else '',
                    Paragraph(escape(item['modelo']), cell_style),
                    Paragraph(str(item['quantidade']), quantity_style),
                ])
            if len(itens_categoria) > 1:
                estilo_tabela.append(
                    ('SPAN', (0, linha_inicio), (0, len(dados_tabela) - 1))
                )
            estilo_tabela.extend([
                ('BACKGROUND', (0, linha_inicio), (0, len(dados_tabela) - 1), verde_claro),
                ('BACKGROUND', (1, linha_inicio), (-1, len(dados_tabela) - 1), cinza_claro),
                ('LINEBELOW', (0, len(dados_tabela) - 1), (-1, len(dados_tabela) - 1), 0.8, linha),
            ])

        total_unidade = sum(item['quantidade'] for item in itens_unidade)
        dados_tabela.append([
            Paragraph('TOTAL DE ITENS ENTREGUES', total_style),
            '',
            Paragraph(str(total_unidade), total_style),
        ])
        estilo_tabela.extend([
            ('SPAN', (0, -1), (1, -1)),
            ('BACKGROUND', (0, -1), (-1, -1), bordô),
            ('LINEABOVE', (0, -1), (-1, -1), 1, bordô),
        ])
        tabela_materiais = Table(
            dados_tabela,
            colWidths=[
                content_width * 0.24,
                content_width * 0.58,
                content_width * 0.18,
            ],
            repeatRows=2,
        )
        tabela_materiais.setStyle(TableStyle(estilo_tabela))
        story.extend([
            tabela_materiais,
            Spacer(1, 12),
            Table(
                [[
                    Paragraph(
                        '<br/>________________________________________<br/>'
                        '<b>RESPONSÁVEL PELO ENVIO</b>',
                        signature_style,
                    ),
                    Paragraph(
                        '<br/>________________________________________<br/>'
                        '<b>RECEBIMENTO / DAP</b>',
                        signature_style,
                    ),
                ]],
                colWidths=[content_width / 2, content_width / 2],
                style=TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TEXTCOLOR', (0, 0), (-1, -1), texto_suave),
                ]),
            ),
        ])

    doc.build(story, onFirstPage=desenhar_identidade_visual, onLaterPages=desenhar_identidade_visual)
    buffer.seek(0)
    return buffer

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
                # 1. Salva no Banco de Dados
                for item in lista:
                    MaterialDescarte.objects.create(
                        unidade=item['unidade'],
                        categoria=item['categoria'],
                        modelo=item['modelo'],
                        quantidade=item['quantidade']
                    )
                
                # 2. Gera um relatório no formato do formulário de entrega da UFPA.
                buffer = gerar_relatorio_entrega(lista)
                
                # 3. Limpa a sessão e retorna o arquivo PDF isolado
                request.session['lista_materiais'] = []
                buffer.seek(0)
                
                response = HttpResponse(buffer, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="relatorio_entregas_ufpa_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
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